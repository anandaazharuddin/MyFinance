from django import forms

from .models import Budget, Category, Goal, Transaction


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ('type', 'category', 'amount', 'description', 'date')

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError('Jumlah harus lebih dari 0.')
        return amount

    def clean_category(self):
        category = self.cleaned_data['category']
        ttype = self.cleaned_data.get('type')
        if ttype and category.type != ttype:
            raise forms.ValidationError('Kategori tidak sesuai dengan jenis transaksi.')
        return category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'type', 'icon', 'color')
        error_messages = {
            'name': {'unique': 'Nama kategori sudah dipakai, coba nama lain.'},
        }


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ('category', 'monthly_limit')

    def clean_category(self):
        category = self.cleaned_data['category']
        if category.type != Category.EXPENSE:
            raise forms.ValidationError('Anggaran hanya berlaku untuk kategori pengeluaran.')
        return category


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ('name', 'target_amount', 'deadline')


class ContributeForm(forms.Form):
    amount = forms.DecimalField(
        label='Jumlah',
        min_value=0.01,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
    )
