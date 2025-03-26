"""
Celery tasks for the loans application.
"""

import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
import os
from django.conf import settings
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from celery import shared_task

from .models import User, Loan, Bill, DailyInterestAccrual


@shared_task
def calculate_credit_score(user_id, aadhar_id):
    """
    Celery task to calculate credit score for a user based on transaction history.
    """
    try:
        # Get the user
        user = User.objects.get(unique_user_id=user_id)
        
        # Read the transactions CSV file
        csv_path = settings.TRANSACTIONS_CSV_PATH
        if not os.path.exists(csv_path):
            user.credit_score = 300  # Default minimum score if CSV doesn't exist
            user.save()
            return f"CSV file not found. Set default credit score for user {user_id}."
        
        df = pd.read_csv(csv_path)
        
        # Filter transactions for the specific user
        user_transactions = df[df['AADHARID'] == aadhar_id]
        
        if user_transactions.empty:
            user.credit_score = 300  # Default minimum score if no transactions
            user.save()
            return f"No transactions found for user {user_id}. Set default credit score."
        
        # Calculate account balance (CREDIT - DEBIT)
        user_transactions['Amount'] = user_transactions['Amount'].astype(float)
        
        # Calculate net balance by transaction type
        balance = 0
        for _, row in user_transactions.iterrows():
            if row['Transaction_type'] == 'CREDIT':
                balance += row['Amount']
            elif row['Transaction_type'] == 'DEBIT':
                balance -= row['Amount']
        
        # Calculate credit score based on account balance
        credit_score = 0
        if balance >= 1000000:  # Rs. 10,00,000
            credit_score = 900
        elif balance <= 100000:  # Rs. 1,00,000
            credit_score = 300
        else:
            # Score adjusts by 10 points for every Rs. 15,000 change in balance
            excess_balance = balance - 100000
            credit_score = 300 + (excess_balance // 15000) * 10
            
            # Cap at 900
            credit_score = min(900, credit_score)
        
        # Update user's credit score
        user.credit_score = int(credit_score)
        user.save()
        
        return f"Credit score calculated successfully for user {user_id}: {credit_score}"
        
    except User.DoesNotExist:
        return f"User with ID {user_id} not found."
    except Exception as e:
        return f"Error calculating credit score: {str(e)}"


@shared_task
def process_daily_billing():
    """
    Celery task to process daily billing for all active loans.
    """
    today = timezone.now().date()
    
    # Get all active loans
    active_loans = Loan.objects.filter(status='ACTIVE')
    
    for loan in active_loans:
        # Calculate days since disbursement
        days_since_disbursement = (today - loan.disbursement_date).days
        
        # Check if this is a billing date (30 days after account creation or last billing)
        latest_bill = Bill.objects.filter(loan=loan).order_by('-billing_date').first()
        
        if latest_bill:
            days_since_last_billing = (today - latest_bill.billing_date).days
            is_billing_date = days_since_last_billing >= 30
        else:
            # First billing should be 30 days after disbursement
            is_billing_date = days_since_disbursement >= 30
        
        # Process daily interest accrual
        daily_interest_rate = loan.calculate_daily_interest_rate()
        daily_interest = loan.principal_balance * (daily_interest_rate / 100)
        
        # Record daily interest accrual
        DailyInterestAccrual.objects.create(
            loan=loan,
            accrual_date=today,
            interest_amount=daily_interest,
            principal_balance=loan.principal_balance
        )
        
        # If this is a billing date, create a new bill
        if is_billing_date:
            with transaction.atomic():
                # Calculate billing period
                if latest_bill:
                    billing_period_start = latest_bill.billing_date + timedelta(days=1)
                else:
                    billing_period_start = loan.disbursement_date
                
                billing_period_end = today
                
                # Calculate interest accrued for the billing period
                interest_accrued = DailyInterestAccrual.objects.filter(
                    loan=loan,
                    accrual_date__gte=billing_period_start,
                    accrual_date__lte=billing_period_end
                ).aggregate(total_interest=Sum('interest_amount'))['total_interest'] or 0
                
                # Calculate minimum due amount
                min_due = loan.calculate_min_due(interest_accrued)
                
                # Check for past due amount
                past_due_amount = 0
                if latest_bill and latest_bill.status != 'PAID':
                    past_due_amount = latest_bill.total_due_amount - latest_bill.amount_paid
                
                # Calculate total due amount
                total_due = min_due + past_due_amount
                
                # Create new bill
                due_date = today + timedelta(days=15)  # Due date is 15 days from billing date
                
                Bill.objects.create(
                    loan=loan,
                    billing_date=today,
                    due_date=due_date,
                    principal_due=loan.principal_balance,
                    interest_accrued=interest_accrued,
                    min_due_amount=min_due,
                    past_due_amount=past_due_amount,
                    total_due_amount=total_due,
                    status='GENERATED'
                )
    
    return f"Daily billing process completed for {active_loans.count()} active loans."
