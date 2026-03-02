"""
Utilities for exporting data to CSV and Excel formats.
"""
import csv
from datetime import datetime
from typing import Any, List, Optional

from django.http import HttpResponse


class CSVExporter:
    """Helper class for exporting querysets to CSV."""
    
    def __init__(self, filename: str, headers: List[str], rows: List[List[Any]]):
        """
        Initialize CSV exporter.
        
        Args:
            filename: Name of the CSV file (without extension)
            headers: List of column headers
            rows: List of rows, where each row is a list of values
        """
        self.filename = filename
        self.headers = headers
        self.rows = rows
    
    def export(self) -> HttpResponse:
        """
        Generate CSV file and return as HTTP response.
        
        Returns:
            HttpResponse with CSV content
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{self.filename}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(self.headers)
        
        for row in self.rows:
            writer.writerow(row)
        
        return response


def export_queryset_to_csv(
    queryset,
    filename: str,
    fields: List[str],
    headers: Optional[List[str]] = None
) -> HttpResponse:
    """
    Export a Django queryset to CSV.
    
    Args:
        queryset: Django queryset to export
        filename: Name of the CSV file (without extension)
        fields: List of model field names to include
        headers: Optional custom headers (defaults to field names)
    
    Returns:
        HttpResponse with CSV content
    
    Example:
        return export_queryset_to_csv(
            Student.objects.all(),
            'students',
            ['id', 'first_name', 'last_name', 'email'],
            ['ID', 'First Name', 'Last Name', 'Email']
        )
    """
    if headers is None:
        headers = fields
    
    rows = []
    for obj in queryset:
        row = []
        for field in fields:
            # Handle nested fields (e.g., 'campus.name')
            if '.' in field:
                parts = field.split('.')
                value = obj
                for part in parts:
                    value = getattr(value, part, '')
                    if value is None:
                        value = ''
                        break
            else:
                value = getattr(obj, field, '')
            
            # Convert to string
            if value is None:
                value = ''
            elif isinstance(value, bool):
                value = 'Yes' if value else 'No'
            elif hasattr(value, '__str__'):
                value = str(value)
            
            row.append(value)
        rows.append(row)
    
    exporter = CSVExporter(filename, headers, rows)
    return exporter.export()


def export_dict_list_to_csv(
    data: List[dict],
    filename: str,
    headers: Optional[List[str]] = None
) -> HttpResponse:
    """
    Export a list of dictionaries to CSV.
    
    Args:
        data: List of dictionaries
        filename: Name of the CSV file (without extension)
        headers: Optional list of headers (defaults to keys from first dict)
    
    Returns:
        HttpResponse with CSV content
    
    Example:
        data = [
            {'name': 'John', 'age': 25},
            {'name': 'Jane', 'age': 30},
        ]
        return export_dict_list_to_csv(data, 'people', ['Name', 'Age'])
    """
    if not data:
        # Empty data
        if headers is None:
            headers = []
        rows = []
    else:
        if headers is None:
            headers = list(data[0].keys())
        
        rows = []
        for item in data:
            row = [item.get(key, '') for key in data[0].keys()]
            rows.append(row)
    
    exporter = CSVExporter(filename, headers, rows)
    return exporter.export()
