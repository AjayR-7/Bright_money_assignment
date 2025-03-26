"""
Models for the loans application.
"""

import uuid
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import models
from django.utils import timezone


class User(models.Model):
    """User model to store user details."""
    
    unique_user_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    aadhar_id = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    annual_income = models.DecimalField(max_digits=12, decimal_places=2)
    credit_score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.aadhar_id})"


class Loan(models.Model):
    """Loan model to store loan details."""
    
    LOAN_STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('CLOSED', 'Closed'),
        ('REJECTED', 'Rejected'),
    )
    
    LOAN_TYPE_CHOICES = (
        ('CREDIT_CARD', 'Credit Card Loan'),
    )
    
    loan_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='loans')
    loan_type = models.CharField(max_length=20, choices=LOAN_TYPE_CHOICES)
    loan_amount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)  # Annual percentage rate (APR)
    term_period = models.IntegerField()  # In months
    disbursement_date = models.DateField()
    status = models.CharField(max_length=10, choices=LOAN_STATUS_CHOICES, default='ACTIVE')
    principal_balance = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Loan {self.loan_id} - {self.user.name}"

    def calculate_daily_interest_rate(self):
        """Calculate daily interest rate from annual interest rate."""
        return round(self.interest_rate / Decimal('365'), 3)

    def calculate_min_due(self, interest_accrued):
        """Calculate minimum due amount for a billing cycle."""
        principal_portion = self.principal_balance * Decimal('0.03')  # 3% of principal
        return principal_portion + interest_accrued


class Payment(models.Model):
    """Payment model to store payment details."""
    
    PAYMENT_STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )
    
    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='COMPLETED')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.payment_id} for Loan {self.loan.loan_id}"


class Bill(models.Model):
    """Bill model to store billing details."""
    
    BILL_STATUS_CHOICES = (
        ('GENERATED', 'Generated'),
        ('PAID', 'Paid'),
        ('PARTIALLY_PAID', 'Partially Paid'),
        ('OVERDUE', 'Overdue'),
    )
    
    bill_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='bills')
    billing_date = models.DateField()
    due_date = models.DateField()
    principal_due = models.DecimalField(max_digits=10, decimal_places=2)
    interest_accrued = models.DecimalField(max_digits=10, decimal_places=2)
    min_due_amount = models.DecimalField(max_digits=10, decimal_places=2)
    past_due_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_due_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=15, choices=BILL_STATUS_CHOICES, default='GENERATED')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bill {self.bill_id} for Loan {self.loan.loan_id}"


class DailyInterestAccrual(models.Model):
    """Model to track daily interest accruals for loans."""
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='interest_accruals')
    accrual_date = models.DateField()
    interest_amount = models.DecimalField(max_digits=10, decimal_places=2)
    principal_balance = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('loan', 'accrual_date')

    def __str__(self):
        return f"Interest accrual for Loan {self.loan.loan_id} on {self.accrual_date}"


class EMISchedule(models.Model):
    """Model to store EMI schedule for loans."""
    
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='emi_schedule')
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('loan', 'due_date')

    def __str__(self):
        return f"EMI for Loan {self.loan.loan_id} due on {self.due_date}"
