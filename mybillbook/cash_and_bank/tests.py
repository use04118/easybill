from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone
from datetime import date, timedelta
from users.models import User, Business
from .models import BankAccount, BankTransaction
from sales.models import Invoice, PaymentIn
from purchase.models import Purchase, PaymentOut

class BankAccountTests(TestCase):
    def setUp(self):
        # Create test user and business
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.business = Business.objects.create(
            name='Test Business',
            owner=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_create_bank_account(self):
        """Test creating a new bank account"""
        url = reverse('bank-account-list')
        data = {
            'account_name': 'Test Bank Account',
            'account_type': 'Bank',
            'opening_balance': 10000,
            'as_of_date': date.today(),
            'bank_account_number': '1234567890',
            'ifsc_code': 'TEST1234567',
            'bank_branch_name': 'Test Branch',
            'account_holder_name': 'Test Holder'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BankAccount.objects.count(), 1)
        self.assertEqual(BankAccount.objects.get().account_name, 'Test Bank Account')

    def test_create_cash_account(self):
        """Test creating a new cash account"""
        url = reverse('bank-account-list')
        data = {
            'account_name': 'Cash Account',
            'account_type': 'Cash',
            'opening_balance': 5000,
            'as_of_date': date.today()
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BankAccount.objects.count(), 1)

    def test_get_bank_account_list(self):
        """Test retrieving bank accounts list"""
        BankAccount.objects.create(
            business=self.business,
            account_name='Test Account',
            account_type='Bank',
            opening_balance=10000,
            as_of_date=date.today()
        )
        url = reverse('bank-account-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_bank_account_detail(self):
        """Test retrieving a single bank account"""
        account = BankAccount.objects.create(
            business=self.business,
            account_name='Test Account',
            account_type='Bank',
            opening_balance=10000,
            as_of_date=date.today()
        )
        url = reverse('bank-account-detail', args=[account.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['account_name'], 'Test Account')

    def test_update_bank_account(self):
        """Test updating a bank account"""
        account = BankAccount.objects.create(
            business=self.business,
            account_name='Test Account',
            account_type='Bank',
            opening_balance=10000,
            as_of_date=date.today()
        )
        url = reverse('bank-account-detail', args=[account.id])
        data = {'account_name': 'Updated Account'}
        response = self.client.patch(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BankAccount.objects.get(id=account.id).account_name, 'Updated Account')

    def test_delete_bank_account(self):
        """Test deleting a bank account"""
        account = BankAccount.objects.create(
            business=self.business,
            account_name='Test Account',
            account_type='Bank',
            opening_balance=10000,
            as_of_date=date.today()
        )
        url = reverse('bank-account-detail', args=[account.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(BankAccount.objects.count(), 0)

class BankTransactionTests(TestCase):
    def setUp(self):
        # Create test user and business
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.business = Business.objects.create(
            name='Test Business',
            owner=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test bank account
        self.account = BankAccount.objects.create(
            business=self.business,
            account_name='Test Account',
            account_type='Bank',
            opening_balance=10000,
            as_of_date=date.today()
        )

    def test_create_add_money_transaction(self):
        """Test creating an add money transaction"""
        url = reverse('bank-transaction-list')
        data = {
            'account': self.account.id,
            'transaction_type': 'ADD',
            'amount': 5000,
            'date': date.today(),
            'notes': 'Test add money'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BankTransaction.objects.count(), 1)
        self.assertEqual(self.account.current_balance, 15000)  # 10000 + 5000

    def test_create_reduce_money_transaction(self):
        """Test creating a reduce money transaction"""
        url = reverse('bank-transaction-list')
        data = {
            'account': self.account.id,
            'transaction_type': 'REDUCE',
            'amount': 3000,
            'date': date.today(),
            'notes': 'Test reduce money'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(BankTransaction.objects.count(), 1)
        self.assertEqual(self.account.current_balance, 7000)  # 10000 - 3000

    def test_create_transfer_transaction(self):
        """Test creating a transfer transaction"""
        # Create destination account
        dest_account = BankAccount.objects.create(
            business=self.business,
            account_name='Destination Account',
            account_type='Bank',
            opening_balance=5000,
            as_of_date=date.today()
        )

        url = reverse('bank-transfer')
        data = {
            'from_account': self.account.id,
            'to_account': dest_account.id,
            'amount': 2000,
            'reference': 'TRANSFER001',
            'notes': 'Test transfer'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify transactions were created
        self.assertEqual(BankTransaction.objects.count(), 2)
        
        # Verify balances
        self.account.refresh_from_db()
        dest_account.refresh_from_db()
        self.assertEqual(self.account.current_balance, 8000)  # 10000 - 2000
        self.assertEqual(dest_account.current_balance, 7000)  # 5000 + 2000

    def test_get_transaction_list(self):
        """Test retrieving transactions list"""
        BankTransaction.objects.create(
            business=self.business,
            account=self.account,
            transaction_type='ADD',
            amount=5000,
            date=date.today()
        )
        url = reverse('bank-transaction-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_get_transaction_detail(self):
        """Test retrieving a single transaction"""
        transaction = BankTransaction.objects.create(
            business=self.business,
            account=self.account,
            transaction_type='ADD',
            amount=5000,
            date=date.today()
        )
        url = reverse('bank-transaction-detail', args=[transaction.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['amount'], '5000.00')

    def test_get_transaction_summary(self):
        """Test retrieving transaction summary"""
        # Create some transactions
        BankTransaction.objects.create(
            business=self.business,
            account=self.account,
            transaction_type='ADD',
            amount=5000,
            date=date.today()
        )
        BankTransaction.objects.create(
            business=self.business,
            account=self.account,
            transaction_type='REDUCE',
            amount=2000,
            date=date.today()
        )

        url = reverse('bank-transaction-summary')
        response = self.client.get(url, {
            'start_date': date.today(),
            'end_date': date.today()
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_credit'], 5000)
        self.assertEqual(response.data['total_debit'], 2000)
        self.assertEqual(response.data['net_balance'], 3000)

    def test_insufficient_balance_transfer(self):
        """Test transfer with insufficient balance"""
        dest_account = BankAccount.objects.create(
            business=self.business,
            account_name='Destination Account',
            account_type='Bank',
            opening_balance=5000,
            as_of_date=date.today()
        )

        url = reverse('bank-transfer')
        data = {
            'from_account': self.account.id,
            'to_account': dest_account.id,
            'amount': 15000,  # More than current balance
            'reference': 'TRANSFER001',
            'notes': 'Test transfer'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Insufficient balance')

    def test_invalid_transaction_date(self):
        """Test creating transaction with future date"""
        url = reverse('bank-transaction-list')
        data = {
            'account': self.account.id,
            'transaction_type': 'ADD',
            'amount': 5000,
            'date': date.today() + timedelta(days=1),  # Future date
            'notes': 'Test future date'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_negative_amount_transaction(self):
        """Test creating transaction with negative amount"""
        url = reverse('bank-transaction-list')
        data = {
            'account': self.account.id,
            'transaction_type': 'ADD',
            'amount': -5000,  # Negative amount
            'date': date.today(),
            'notes': 'Test negative amount'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

class BankAccountBalanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        self.business = Business.objects.create(
            name='Test Business',
            owner=self.user
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.account = BankAccount.objects.create(
            business=self.business,
            account_name='Test Account',
            account_type='Bank',
            opening_balance=10000,
            as_of_date=date.today()
        )

    def test_get_account_balance(self):
        """Test retrieving account balance"""
        url = reverse('bank-account-balance', args=[self.account.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_balance'], '10000.00')
        self.assertEqual(response.data['account_name'], 'Test Account')

    def test_get_nonexistent_account_balance(self):
        """Test retrieving balance for nonexistent account"""
        url = reverse('bank-account-balance', args=[999])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_balance_after_transactions(self):
        """Test balance after multiple transactions"""
        # Create some transactions
        BankTransaction.objects.create(
            business=self.business,
            account=self.account,
            transaction_type='ADD',
            amount=5000,
            date=date.today()
        )
        BankTransaction.objects.create(
            business=self.business,
            account=self.account,
            transaction_type='REDUCE',
            amount=2000,
            date=date.today()
        )

        url = reverse('bank-account-balance', args=[self.account.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_balance'], '13000.00')  # 10000 + 5000 - 2000
