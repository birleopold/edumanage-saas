from django.contrib import admin

from .models import Author, Book, BookCopy, BookLoan, Category, Fine, Reservation


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'isbn', 'category', 'published_year', 'total_copies', 'is_active')
    list_filter = ('is_active', 'category', 'published_year')
    search_fields = ('title', 'isbn', 'publisher')
    filter_horizontal = ('authors',)


@admin.register(BookCopy)
class BookCopyAdmin(admin.ModelAdmin):
    list_display = ('book', 'copy_code', 'barcode', 'status', 'location', 'is_active')
    list_filter = ('status', 'is_active')
    search_fields = ('copy_code', 'barcode', 'book__title')


@admin.register(BookLoan)
class BookLoanAdmin(admin.ModelAdmin):
    list_display = ('copy', 'borrower_type', 'student', 'staff', 'borrowed_at', 'due_date', 'status')
    list_filter = ('status', 'borrower_type', 'borrowed_at')
    search_fields = ('copy__copy_code', 'student__first_name', 'student__last_name', 'staff__first_name', 'staff__last_name')
    date_hierarchy = 'borrowed_at'


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('book', 'borrower_type', 'student', 'staff', 'status', 'reserved_at')
    list_filter = ('status', 'borrower_type')
    search_fields = ('book__title', 'student__first_name', 'student__last_name', 'staff__first_name', 'staff__last_name')
    date_hierarchy = 'reserved_at'


@admin.register(Fine)
class FineAdmin(admin.ModelAdmin):
    list_display = ('loan', 'borrower_type', 'student', 'staff', 'amount', 'status', 'issued_at')
    list_filter = ('status', 'borrower_type')
    search_fields = ('student__first_name', 'student__last_name', 'staff__first_name', 'staff__last_name', 'reason')
    date_hierarchy = 'issued_at'
    readonly_fields = ('issued_at', 'paid_at', 'waived_at')
