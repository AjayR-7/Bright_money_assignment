"""
Utility functions for the loans application.
"""

from decimal import Decimal
from datetime import datetime, timedelta


def calculate_emi(principal, rate, time):
    """
    Calculate Equated Monthly Installment (EMI).
    
    Args:
        principal: Principal loan amount
        rate: Annual interest rate in percentage
        time: Loan tenure in months
    
    Returns:
        Monthly EMI amount
    """
    # Convert rate from percentage to decimal and then to monthly rate
    monthly_rate = Decimal(rate) / 100 / 12
    
    # EMI formula: P * r * (1+r)^n / ((1+r)^n - 1)
    numerator = principal * monthly_rate * (1 + monthly_rate) ** time
    denominator = (1 + monthly_rate) ** time - 1
    
    if denominator == 0:  # Handle case when interest rate is 0
        return principal / time
    
    emi = numerator / denominator
    return round(emi, 2)


def calculate_minimum_due(principal, interest_accrued):
    """
    Calculate minimum due amount for a billing cycle.
    
    Args:
        principal: Current principal balance
        interest_accrued: Interest accrued for the billing cycle
    
    Returns:
        Minimum due amount
    """
    principal_portion = principal * Decimal('0.03')  # 3% of principal
    return principal_portion + interest_accrued


def calculate_daily_interest(principal, annual_rate):
    """
    Calculate daily interest amount.
    
    Args:
        principal: Current principal balance
        annual_rate: Annual interest rate in percentage
    
    Returns:
        Daily interest amount
    """
    daily_rate = round(Decimal(annual_rate) / Decimal('365'), 3)
    return principal * (daily_rate / 100)


def calculate_credit_score_from_balance(balance):
    """
    Calculate credit score based on account balance.
    
    Args:
        balance: Account balance in rupees
    
    Returns:
        Credit score between 300 and 900
    """
    if balance >= 1000000:  # Rs. 10,00,000
        return 900
    elif balance <= 100000:  # Rs. 1,00,000
        return 300
    else:
        # Score adjusts by 10 points for every Rs. 15,000 change in balance
        excess_balance = balance - 100000
        credit_score = 300 + (excess_balance // 15000) * 10
        
        # Cap at 900
        return min(900, credit_score)
