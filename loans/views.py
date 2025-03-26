"""
Views for the loans application.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse

from .models import User, Loan, Payment, Bill, EMISchedule
from .serializers import (
    RegisterUserSerializer, LoanApplicationSerializer, 
    PaymentSerializer, StatementSerializer,
    EMIDateAmountSerializer, PastTransactionSerializer,
    UpcomingTransactionSerializer
)
# Import utility functions directly
from .utils import calculate_credit_score_from_balance


def index(request):
    """
    View for the root path to show available API endpoints.
    """
    # For API clients, return JSON if requested
    if request.META.get('HTTP_ACCEPT') == 'application/json':
        api_endpoints = {
            "endpoints": [
                {
                    "path": "/api/register-user/",
                    "method": "POST",
                    "description": "Register a new user"
                },
                {
                    "path": "/api/apply-loan/",
                    "method": "POST",
                    "description": "Apply for a loan"
                },
                {
                    "path": "/api/make-payment/",
                    "method": "POST",
                    "description": "Make a payment for a loan"
                },
                {
                    "path": "/api/get-statement/",
                    "method": "GET",
                    "description": "Get loan statement details"
                }
            ],
            "project_name": "Credit Service API",
            "version": "1.0"
        }
        return JsonResponse(api_endpoints)
    
    # For browsers, render the interactive HTML page
    return render(request, 'index.html', {
        'project_name': 'Credit Service API',
        'version': '1.0'
    })


class RegisterUserView(APIView):
    """
    API view for user registration.
    """
    
    def post(self, request):
        serializer = RegisterUserSerializer(data=request.data)
        if not serializer.is_valid():
            # Convert validation errors to a simple string message
            error_message = ""
            for field, errors in serializer.errors.items():
                error_message += f"{field}: {' '.join(errors)} "
            return Response({"error": error_message.strip()}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract validated data
        aadhar_id = serializer.validated_data.get('aadhar_id')
        name = serializer.validated_data.get('name')
        email = serializer.validated_data.get('email_id')
        annual_income = serializer.validated_data.get('annual_income')
        
        # Check if user with the same Aadhar ID already exists
        if User.objects.filter(aadhar_id=aadhar_id).exists():
            return Response({"error": "User with this Aadhar ID already exists."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user with the same email already exists
        if User.objects.filter(email=email).exists():
            return Response({"error": "User with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Create new user
        user = User.objects.create(
            aadhar_id=aadhar_id,
            name=name,
            email=email,
            annual_income=annual_income
        )
        
        # Calculate credit score synchronously
        try:
            import pandas as pd
            import os
            from django.conf import settings
            
            # Read the transactions CSV file
            csv_path = settings.TRANSACTIONS_CSV_PATH
            if not os.path.exists(csv_path):
                user.credit_score = 300  # Default minimum score if CSV doesn't exist
                user.save()
            else:
                df = pd.read_csv(csv_path)
                
                # Filter transactions for the specific user
                user_transactions = df[df['AADHARID'] == aadhar_id]
                
                if user_transactions.empty:
                    user.credit_score = 300  # Default minimum score if no transactions
                else:
                    # Calculate account balance (CREDIT - DEBIT)
                    user_transactions['Amount'] = user_transactions['Amount'].astype(float)
                    
                    # Calculate credit and debit separately
                    credits = user_transactions[user_transactions['Transaction_type'] == 'CREDIT']['Amount'].sum()
                    debits = user_transactions[user_transactions['Transaction_type'] == 'DEBIT']['Amount'].sum()
                    
                    # Calculate net balance
                    balance = credits - debits
                    
                    print(f"User {aadhar_id} - Credits: {credits}, Debits: {debits}, Balance: {balance}")
                    
                    # Calculate credit score based on account balance
                    if balance >= 1000000:  # Rs. 10,00,000
                        credit_score = 900
                    elif balance <= 100000:  # Rs. 1,00,000
                        credit_score = 300
                    else:
                        # Score adjusts by 10 points for every Rs. 15,000 change in balance
                        excess_balance = balance - 100000
                        credit_score = 300 + int((excess_balance / 15000) * 10)
                        
                        # Cap at 900
                        credit_score = min(900, credit_score)
                    
                    print(f"Calculated credit score: {credit_score}")
                    
                    # Make sure credit score is above 450 for users with high balances
                    if balance >= 500000:  # Rs. 5,00,000
                        credit_score = max(credit_score, 700)
                    elif balance >= 250000:  # Rs. 2,50,000
                        credit_score = max(credit_score, 600)
                    elif balance >= 150000:  # Rs. 1,50,000
                        credit_score = max(credit_score, 500)
                    
                    # Update user's credit score
                    user.credit_score = int(credit_score)
                
                user.save()
        except Exception as e:
            # Log the error but continue
            print(f"Error calculating credit score: {str(e)}")
        
        # Return success response
        return Response({
            "error": None,
            "unique_user_id": user.unique_user_id
        }, status=status.HTTP_200_OK)


class ApplyLoanView(APIView):
    """
    API view for loan application.
    """
    
    def post(self, request):
        serializer = LoanApplicationSerializer(data=request.data)
        if not serializer.is_valid():
            # Convert validation errors to a simple string message
            error_message = ""
            for field, errors in serializer.errors.items():
                error_message += f"{field}: {' '.join(errors)} "
            return Response({"error": error_message.strip()}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract validated data
        unique_user_id = serializer.validated_data.get('unique_user_id')
        loan_type = serializer.validated_data.get('loan_type')
        loan_amount = serializer.validated_data.get('loan_amount')
        interest_rate = serializer.validated_data.get('interest_rate')
        term_period = serializer.validated_data.get('term_period')
        disbursement_date = serializer.validated_data.get('disbursement_date')
        
        try:
            # Get user
            user = User.objects.get(unique_user_id=unique_user_id)
            
            # Check credit score
            if not user.credit_score or user.credit_score < 300:
                return Response({
                    "error": "Loan application rejected. Credit score is too low."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            print(f"User credit score: {user.credit_score}")
            
            # Check annual income
            if user.annual_income < 150000:  # Rs. 1,50,000
                return Response({
                    "error": "Loan application rejected. Annual income is below the minimum requirement."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check loan amount (already validated in serializer)
            
            # Calculate monthly income
            monthly_income = user.annual_income / 12
            
            # Calculate EMI amount for first month (principal portion + interest)
            principal_portion = loan_amount * Decimal('0.03')  # 3% of principal
            monthly_interest = (loan_amount * interest_rate / 100) / 12
            emi_amount = principal_portion + monthly_interest
            
            # Check if EMI exceeds 20% of monthly income
            if emi_amount > (monthly_income * Decimal('0.2')):
                return Response({
                    "error": "Loan application rejected. EMI exceeds 20% of monthly income."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if monthly interest is at least Rs. 50
            if monthly_interest < 50:
                return Response({
                    "error": "Loan application rejected. Monthly interest is below the minimum requirement."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create loan with atomic transaction
            with transaction.atomic():
                loan = Loan.objects.create(
                    user=user,
                    loan_type=loan_type,
                    loan_amount=loan_amount,
                    interest_rate=interest_rate,
                    term_period=term_period,
                    disbursement_date=disbursement_date,
                    principal_balance=loan_amount,
                    status='ACTIVE'
                )
                
                # Calculate EMI schedule
                due_dates = []
                remaining_principal = loan_amount
                
                for month in range(1, term_period + 1):
                    due_date = disbursement_date + timedelta(days=30 * month)
                    
                    # Calculate interest for this month
                    monthly_interest = (remaining_principal * interest_rate / 100) / 12
                    
                    # Calculate principal portion (3% of the original principal)
                    principal_portion = loan_amount * Decimal('0.03')
                    
                    # For the last month, adjust to pay all remaining principal
                    if month == term_period:
                        amount_due = remaining_principal + monthly_interest
                    else:
                        amount_due = principal_portion + monthly_interest
                        remaining_principal -= principal_portion
                    
                    # Round to nearest integer
                    amount_due = round(amount_due)
                    
                    # Create EMI schedule entry
                    EMISchedule.objects.create(
                        loan=loan,
                        due_date=due_date,
                        amount_due=amount_due
                    )
                    
                    due_dates.append({
                        "date": due_date.strftime('%Y-%m-%d'),
                        "amount_due": amount_due
                    })
            
            # Return success response with loan details
            return Response({
                "error": None,
                "loan_id": loan.loan_id,
                "due_dates": due_dates
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                "error": "User not found."
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class MakePaymentView(APIView):
    """
    API view for processing loan payments.
    """
    
    def post(self, request):
        serializer = PaymentSerializer(data=request.data)
        if not serializer.is_valid():
            # Convert validation errors to a simple string message
            error_message = ""
            for field, errors in serializer.errors.items():
                error_message += f"{field}: {' '.join(errors)} "
            return Response({"error": error_message.strip()}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract validated data
        loan_id = serializer.validated_data.get('loan_id')
        amount = serializer.validated_data.get('amount')
        
        try:
            # Get loan
            loan = Loan.objects.get(loan_id=loan_id)
            
            # Check if loan is active
            if loan.status != 'ACTIVE':
                return Response({
                    "error": f"Payment rejected. Loan is not active, current status: {loan.status}."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get upcoming EMIs that are not paid
            unpaid_emis = EMISchedule.objects.filter(
                loan=loan,
                is_paid=False
            ).order_by('due_date')
            
            if not unpaid_emis:
                return Response({
                    "error": "Payment rejected. No pending EMIs found."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if trying to pay for future EMIs before past EMIs
            earliest_unpaid_emi = unpaid_emis[0]
            
            # Check if payment matches the due amount for the earliest unpaid EMI
            if amount != earliest_unpaid_emi.amount_due:
                return Response({
                    "error": f"Payment rejected. The amount does not match the due installment of ₹{earliest_unpaid_emi.amount_due}."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Process payment with atomic transaction
            with transaction.atomic():
                # Create payment record
                payment = Payment.objects.create(
                    loan=loan,
                    amount=amount,
                    payment_date=timezone.now(),
                    status='COMPLETED'
                )
                
                # Update EMI schedule
                earliest_unpaid_emi.is_paid = True
                earliest_unpaid_emi.save()
                
                # Update principal balance
                # Get current bill
                current_bill = Bill.objects.filter(
                    loan=loan,
                    status__in=['GENERATED', 'PARTIALLY_PAID']
                ).order_by('-billing_date').first()
                
                if current_bill:
                    # Update bill status
                    if current_bill.amount_paid + amount >= current_bill.total_due_amount:
                        current_bill.status = 'PAID'
                    else:
                        current_bill.status = 'PARTIALLY_PAID'
                    
                    current_bill.amount_paid += amount
                    current_bill.save()
                
                # Reduce the principal balance by the principal portion (excluding interest)
                if loan.principal_balance > 0:
                    # Calculate interest portion
                    interest_portion = (loan.principal_balance * loan.interest_rate / 100) / 12
                    principal_portion = amount - interest_portion
                    
                    # Ensure we don't go below zero
                    loan.principal_balance = max(0, loan.principal_balance - principal_portion)
                    
                    # If principal balance is zero, check if all EMIs are paid
                    if loan.principal_balance == 0 and not EMISchedule.objects.filter(loan=loan, is_paid=False).exists():
                        loan.status = 'CLOSED'
                    
                    loan.save()
            
            # Return success response
            return Response({
                "error": None,
                "message": f"Payment of ₹{amount} recorded successfully."
            }, status=status.HTTP_200_OK)
            
        except Loan.DoesNotExist:
            return Response({
                "error": "Loan not found."
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)


class GetStatementView(APIView):
    """
    API view for fetching loan statements.
    """
    
    def get(self, request):
        serializer = StatementSerializer(data=request.query_params)
        if not serializer.is_valid():
            # Convert validation errors to a simple string message
            error_message = ""
            for field, errors in serializer.errors.items():
                error_message += f"{field}: {' '.join(errors)} "
            return Response({"error": error_message.strip()}, status=status.HTTP_400_BAD_REQUEST)
        
        # Extract validated data
        loan_id = serializer.validated_data.get('loan_id')
        
        try:
            # Get loan
            loan = get_object_or_404(Loan, loan_id=loan_id)
            
            # Check if loan is closed
            if loan.status == 'CLOSED':
                return Response({
                    "error": "Loan does not exist or has been closed."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get past transactions (paid EMIs)
            past_transactions = []
            paid_emis = EMISchedule.objects.filter(
                loan=loan,
                is_paid=True
            ).order_by('due_date')
            
            for emi in paid_emis:
                # Get corresponding payment - don't restrict to the exact due date
                payment = Payment.objects.filter(
                    loan=loan
                ).order_by('payment_date').first()
                
                if payment:
                    # Calculate principal and interest portions more accurately
                    # Calculate interest portion (monthly interest)
                    monthly_interest = (loan.loan_amount * loan.interest_rate / 100) / 12
                    # Principal is the payment amount minus the interest
                    principal_portion = payment.amount - monthly_interest
                    
                    # Round values to 2 decimal places for readability
                    past_transactions.append({
                        "date": emi.due_date.strftime('%Y-%m-%d'),
                        "principal_due": round(principal_portion, 2),
                        "interest": round(monthly_interest, 2),
                        "amount_paid": round(payment.amount, 2)
                    })
            
            # Get upcoming transactions (unpaid EMIs)
            upcoming_transactions = []
            unpaid_emis = EMISchedule.objects.filter(
                loan=loan,
                is_paid=False
            ).order_by('due_date')
            
            for emi in unpaid_emis:
                upcoming_transactions.append({
                    "date": emi.due_date.strftime('%Y-%m-%d'),
                    "amount_due": round(emi.amount_due, 2)
                })
            
            # Return success response
            return Response({
                "error": None,
                "past_transactions": past_transactions,
                "upcoming_transactions": upcoming_transactions
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
