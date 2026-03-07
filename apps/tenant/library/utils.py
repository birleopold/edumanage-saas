import io
import random
import string

try:
    import barcode
    from barcode.writer import ImageWriter
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False


def generate_copy_code(book_id: int, sequence: int = 1) -> str:
    """Generate a unique copy code for a book."""
    return f"BK{book_id:06d}-{sequence:03d}"


def generate_barcode_number() -> str:
    """Generate a random barcode number (EAN13 format)."""
    # Generate 12 random digits, the 13th will be calculated as checksum
    digits = ''.join(random.choices(string.digits, k=12))
    
    # Calculate EAN13 checksum
    odd_sum = sum(int(digits[i]) for i in range(0, 12, 2))
    even_sum = sum(int(digits[i]) for i in range(1, 12, 2))
    checksum = (10 - ((odd_sum + even_sum * 3) % 10)) % 10
    
    return digits + str(checksum)


def generate_barcode_image(barcode_number: str) -> bytes:
    """
    Generate a barcode image for the given number.
    Returns image bytes in PNG format.
    """
    if not BARCODE_AVAILABLE:
        return None
    
    try:
        # Use EAN13 barcode format
        ean = barcode.get('ean13', barcode_number, writer=ImageWriter())
        
        # Generate to BytesIO
        buffer = io.BytesIO()
        ean.write(buffer)
        buffer.seek(0)
        
        return buffer.getvalue()
    except Exception:
        return None


def generate_qr_code(data: str, size: int = 10) -> bytes:
    """
    Generate a QR code image for the given data.
    Returns image bytes in PNG format.
    """
    if not QRCODE_AVAILABLE:
        return None
    
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        return buffer.getvalue()
    except Exception:
        return None


def get_overdue_loans():
    """Get all overdue loans."""
    from django.utils import timezone
    from .models import BookLoan
    
    return BookLoan.objects.filter(
        status=BookLoan.OPEN,
        due_date__lt=timezone.now().date()
    ).select_related('copy', 'copy__book', 'student', 'staff')


def get_popular_books(limit=10):
    """Get most borrowed books."""
    from django.db.models import Count
    from .models import Book
    
    return Book.objects.annotate(
        loan_count=Count('copies__loans')
    ).order_by('-loan_count')[:limit]


def get_book_availability(book):
    """Get availability statistics for a book."""
    from .models import BookCopy
    
    total = book.copies.filter(is_active=True).count()
    available = book.copies.filter(status=BookCopy.AVAILABLE, is_active=True).count()
    checked_out = book.copies.filter(status=BookCopy.CHECKED_OUT, is_active=True).count()
    
    return {
        'total': total,
        'available': available,
        'checked_out': checked_out,
        'availability_percent': (available / total * 100) if total > 0 else 0
    }
