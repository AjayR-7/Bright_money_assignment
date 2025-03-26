"""
Serializers for the loans application.
"""

from rest_framework import serializers
from decimal import Decimal
from datetime import datetime, timedelta
from .models import User, Loan, Payment, Bill, EMISchedule


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['unique_user_id', 'aadhar_id', 'name', 'email', 'annual_income', 'credit_score']
        read_only_fields = ['unique_user_id', 'credit_score']


class RegisterUserSerializer(serializers.Serializer):
    """Serializer for user registration."""
    
    aadhar_id = serializers.CharField(max_length=12)
    name = serializers.CharField(max_length=255)
    email_id = serializers.EmailField()
    annual_income = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate_aadhar_id(self, value):
        """Validate aadhar_id format."""
        if not value.isdigit() or len(value) != 12:
            raise serializers.ValidationError("Aadhar ID must be a 12-digit number.")
        return value

    def validate_annual_income(self, value):
        """Validate annual_income is positive."""
        if value <= 0:
            raise serializers.ValidationError("Annual income must be positive.")
        return value


class EMIDateAmountSerializer(serializers.Serializer):
    """Serializer for EMI date and amount."""
    
    date = serializers.DateField()
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2)


class LoanApplicationSerializer(serializers.Serializer):
    """Serializer for loan application."""
    
    unique_user_id = serializers.UUIDField()
    loan_type = serializers.CharField(max_length=20)
    loan_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = serializers.DecimalField(max_digits=5, decimal_places=2)
    term_period = serializers.IntegerField()
    disbursement_date = serializers.DateField()

    def validate_loan_type(self, value):
        """Validate loan_type is a valid type."""
        valid_types = [choice[0] for choice in Loan.LOAN_TYPE_CHOICES]
        if value not in valid_types and value != "Credit Card Loan":
            raise serializers.ValidationError(f"Loan type must be one of: {', '.join(valid_types)}")
        if value == "Credit Card Loan":
            return "CREDIT_CARD"
        return value

    def validate_loan_amount(self, value):
        """Validate loan_amount is positive and within limits."""
        if value <= 0:
            raise serializers.ValidationError("Loan amount must be positive.")
        if value > 5000:
            raise serializers.ValidationError("Loan amount cannot exceed Rs. 5000.")
        return value

    def validate_interest_rate(self, value):
        """Validate interest_rate is within acceptable range."""
        if value < 12:
            raise serializers.ValidationError("Interest rate must be at least 12%.")
        return value

    def validate_term_period(self, value):
        """Validate term_period is positive."""
        if value <= 0:
            raise serializers.ValidationError("Term period must be positive.")
        return value


class PaymentSerializer(serializers.Serializer):
    """Serializer for payment processing."""
    
    loan_id = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate_amount(self, value):
        """Validate amount is positive."""
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be positive.")
        return value


class StatementSerializer(serializers.Serializer):
    """Serializer for loan statement."""
    
    loan_id = serializers.UUIDField()


class PastTransactionSerializer(serializers.Serializer):
    """Serializer for past transaction details."""
    
    date = serializers.DateField()
    principal_due = serializers.DecimalField(max_digits=10, decimal_places=2)
    interest = serializers.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = serializers.DecimalField(max_digits=10, decimal_places=2)


class UpcomingTransactionSerializer(serializers.Serializer):
    """Serializer for upcoming transaction details."""
    
    date = serializers.DateField()
    amount_due = serializers.DecimalField(max_digits=10, decimal_places=2)
