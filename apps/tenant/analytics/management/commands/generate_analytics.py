from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from apps.tenant.academics.models import AcademicTerm, Stream
from apps.tenant.students.models import StudentProfile
from apps.tenant.analytics.utils import (
    calculate_student_performance_snapshot,
    generate_class_performance_report,
)


class Command(BaseCommand):
    help = 'Generate performance analytics snapshots for students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--term',
            type=int,
            help='Academic term ID',
        )
        parser.add_argument(
            '--stream',
            type=int,
            help='Stream ID (optional, generates for all if not specified)',
        )
        parser.add_argument(
            '--current',
            action='store_true',
            help='Use current academic term',
        )

    def handle(self, *args, **options):
        # Determine term
        if options['current']:
            term = AcademicTerm.objects.filter(is_current=True).first()
            if not term:
                raise CommandError('No current academic term found')
        elif options['term']:
            try:
                term = AcademicTerm.objects.get(id=options['term'])
            except AcademicTerm.DoesNotExist:
                raise CommandError(f'Term with ID {options["term"]} does not exist')
        else:
            raise CommandError('Please specify --term <id> or --current')

        self.stdout.write(self.style.SUCCESS(f'Generating analytics for term: {term}'))

        # Get students
        students = StudentProfile.objects.filter(is_active=True)
        if options['stream']:
            try:
                stream = Stream.objects.get(id=options['stream'])
                students = students.filter(stream=stream)
                self.stdout.write(f'Filtering by stream: {stream}')
            except Stream.DoesNotExist:
                raise CommandError(f'Stream with ID {options["stream"]} does not exist')

        total = students.count()
        if total == 0:
            self.stdout.write(self.style.WARNING('No students found'))
            return

        self.stdout.write(f'Processing {total} students...')

        # Generate snapshots
        success_count = 0
        error_count = 0
        
        for i, student in enumerate(students, 1):
            try:
                calculate_student_performance_snapshot(student, term)
                success_count += 1
                
                # Progress indicator
                if i % 10 == 0:
                    self.stdout.write(f'  Processed {i}/{total} students...', ending='\r')
                    
            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Error processing {student}: {str(e)}')
                )

        self.stdout.write('\n')
        self.stdout.write(
            self.style.SUCCESS(
                f'✓ Successfully generated {success_count} snapshots'
            )
        )
        
        if error_count > 0:
            self.stdout.write(
                self.style.WARNING(f'✗ {error_count} errors encountered')
            )

        # Generate class reports
        if not options['stream']:
            self.stdout.write('\nGenerating class performance reports...')
            streams = Stream.objects.filter(is_active=True).annotate(
                student_count=Count('students')
            ).filter(student_count__gt=0)
            
            for stream in streams:
                try:
                    generate_class_performance_report(stream, term)
                    self.stdout.write(f'  ✓ {stream}')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ✗ {stream}: {str(e)}')
                    )
        
        self.stdout.write('\n' + self.style.SUCCESS('Analytics generation complete!'))
