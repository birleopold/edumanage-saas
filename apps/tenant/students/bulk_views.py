from django.contrib import messages
from django.shortcuts import redirect, render
from django.http import HttpResponse

from apps.tenant.orgsettings.models import Campus
from apps.tenant.orgsettings.services import get_or_create_organization, get_current_campus
from apps.tenant.portals.permissions import role_required
from apps.tenant.users.models import Role

from .bulk_import import (
    parse_csv_file,
    parse_excel_file,
    process_bulk_import,
    generate_credentials_pdf,
    send_bulk_setup_emails
)


@role_required(Role.ADMIN)
def bulk_import_students(request):
    """Handle bulk student import via CSV/Excel upload."""
    org = get_or_create_organization()
    current_campus = get_current_campus(request)
    
    if request.method == "POST":
        uploaded_file = request.FILES.get('import_file')
        create_users = request.POST.get('create_users') == 'on'
        send_emails = request.POST.get('send_emails') == 'on'
        
        if not uploaded_file:
            messages.error(request, "Please select a file to upload.")
            return redirect("admin_students_bulk_import")
        
        # Build campus map
        campuses = Campus.objects.filter(organization=org)
        campus_map = {c.code: c for c in campuses if c.code}
        
        default_campus = current_campus or campuses.first()
        
        if not default_campus:
            messages.error(request, "No campus found. Please create a campus first.")
            return redirect("admin_students_bulk_import")
        
        # Parse file based on extension
        filename = uploaded_file.name.lower()
        try:
            if filename.endswith('.csv'):
                rows = parse_csv_file(uploaded_file, campus_map)
            elif filename.endswith(('.xlsx', '.xls')):
                rows = parse_excel_file(uploaded_file, campus_map)
            else:
                messages.error(request, "Invalid file format. Please upload CSV or Excel file.")
                return redirect("admin_students_bulk_import")
        except Exception as e:
            messages.error(request, f"Error parsing file: {str(e)}")
            return redirect("admin_students_bulk_import")
        
        if not rows:
            messages.error(request, "No valid rows found in the file.")
            return redirect("admin_students_bulk_import")
        
        # Process import
        result = process_bulk_import(
            rows=rows,
            default_campus=default_campus,
            campus_map=campus_map,
            create_users=create_users,
            admin_user=request.user
        )
        
        # Store credentials in session for download/email
        if result.credentials:
            request.session['bulk_import_credentials'] = [
                {
                    'student_id': c['student'].pk,
                    'student_number': c['username'],
                    'first_name': c['student'].first_name,
                    'last_name': c['student'].last_name,
                    'email': c['student'].email,
                    'temp_password': c['temp_password'],
                    'has_setup_token': bool(c['setup_token']),
                }
                for c in result.credentials
            ]
        
        # Display results
        if result.errors:
            for error in result.errors[:10]:  # Show first 10 errors
                messages.warning(request, error)
            if len(result.errors) > 10:
                messages.warning(request, f"... and {len(result.errors) - 10} more errors")
        
        if result.successful > 0:
            messages.success(
                request,
                f"Successfully imported {result.successful} student(s). "
                f"{result.failed} failed."
            )
            
            # Send emails if requested
            if send_emails and result.credentials:
                sent_count = send_bulk_setup_emails(result.credentials, request, request.user)
                if sent_count > 0:
                    messages.success(request, f"Setup emails sent to {sent_count} student(s).")
            
            # Redirect to results page
            return redirect("admin_students_bulk_import_results")
        else:
            messages.error(request, "Import failed. Please check the errors above.")
            return redirect("admin_students_bulk_import")
    
    return render(request, "portals/admin/students/bulk_import.html", {
        "current_campus": current_campus,
    })


@role_required(Role.ADMIN)
def bulk_import_results(request):
    """Display bulk import results with download options."""
    credentials = request.session.get('bulk_import_credentials', [])
    
    if not credentials:
        messages.info(request, "No import results available.")
        return redirect("admin_students_bulk_import")
    
    return render(request, "portals/admin/students/bulk_import_results.html", {
        "credentials": credentials,
    })


@role_required(Role.ADMIN)
def download_credentials_csv(request):
    """Download credentials as CSV file."""
    credentials = request.session.get('bulk_import_credentials', [])
    
    if not credentials:
        messages.error(request, "No credentials available for download.")
        return redirect("admin_students_bulk_import")
    
    import csv
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="student_credentials_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Student Number', 'First Name', 'Last Name', 'Email', 'Temporary Password'])
    
    for cred in credentials:
        writer.writerow([
            cred['student_number'],
            cred['first_name'],
            cred['last_name'],
            cred['email'],
            cred['temp_password'],
        ])
    
    return response


@role_required(Role.ADMIN)
def download_sample_template(request):
    """Download a sample CSV template for bulk import."""
    import csv
    from datetime import datetime
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_import_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['first_name', 'last_name', 'date_of_birth', 'email', 'campus_code'])
    writer.writerow(['John', 'Doe', '2010-05-15', 'john.doe@example.com', 'MAIN'])
    writer.writerow(['Jane', 'Smith', '2011-08-22', 'jane.smith@example.com', 'BRANCH'])
    writer.writerow(['Bob', 'Johnson', '2009-12-03', '', 'MAIN'])
    
    return response
