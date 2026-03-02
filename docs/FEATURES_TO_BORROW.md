# Features to Borrow from Existing Apps

## Analysis of Existing Apps in the System

After analyzing all 22 apps in the `apps/tenant/` directory, here are valuable features and patterns we can borrow and implement to enhance our system:

---

## 1. **Status Tracking & Workflow Management** ⭐⭐⭐

### What We Have
- Basic status fields in some models
- Simple OPEN/CLOSED states

### What We Can Borrow

**From Admissions App:**
- Multi-stage workflow: `NEW → IN_REVIEW → ADMITTED → REJECTED`
- Status transitions with validation
- Audit trail of status changes

**From Discipline App:**
- Severity levels: `LOW`, `MEDIUM`, `HIGH`
- Action tracking with `IncidentAction` model
- Related actions linked to main record

**From Library App:**
- Item status tracking: `AVAILABLE`, `LOST`, `DAMAGED`
- Loan status: `OPEN`, `RETURNED`
- Due date management with overdue detection

**Implementation Ideas:**
```python
# Add to models with workflows
class StatusHistory(models.Model):
    """Track status changes for audit trail"""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    old_status = models.CharField(max_length=32)
    new_status = models.CharField(max_length=32)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

---

## 2. **Inventory & Stock Management** ⭐⭐⭐

### What We Have
- Basic CRUD for resources
- No stock tracking

### What We Can Borrow from Inventory App

**Stock Movement Tracking:**
- `IN`, `OUT`, `ADJUST` movement types
- Calculated stock on hand: `stock_on_hand()` method
- Movement history with references
- Decimal precision for quantities

**Asset Assignment:**
- Track who has what equipment
- Assignment to users or students
- Return tracking with dates
- Status: `ACTIVE`, `RETURNED`

**Implementation Ideas:**
```python
# Add to any resource that needs stock tracking
def stock_on_hand(self) -> Decimal:
    """Calculate current stock from movements"""
    totals = self.movements.aggregate(
        in_qty=Sum("quantity", filter=Q(movement_type='IN')),
        out_qty=Sum("quantity", filter=Q(movement_type='OUT')),
        adj_qty=Sum("quantity", filter=Q(movement_type='ADJUST')),
    )
    in_qty = totals.get("in_qty") or Decimal("0")
    out_qty = totals.get("out_qty") or Decimal("0")
    adj_qty = totals.get("adj_qty") or Decimal("0")
    return in_qty - out_qty + adj_qty
```

**Use Cases:**
- Track textbooks, uniforms, equipment
- Lab equipment checkout
- Sports equipment management
- Library book copies (already has this!)

---

## 3. **Hierarchical Resource Management** ⭐⭐⭐

### What We Can Borrow

**From Hostels App:**
- 3-level hierarchy: `Hostel → HostelRoom → Bed`
- Capacity tracking at each level
- Unique constraints ensuring data integrity
- Allocation with status tracking

**From Transport App:**
- Route → Stop hierarchy with ordering
- Time scheduling (pickup/dropoff times)
- Location notes for each stop

**From Timetable App:**
- Period management with time slots
- Room allocation
- Conflict detection (unique_together constraints)

**Implementation Ideas:**
```python
# Generic hierarchical resource pattern
class ResourceCategory(models.Model):
    name = models.CharField(max_length=128)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    level = models.PositiveSmallIntegerField(default=0)
    
    def get_ancestors(self):
        """Get all parent categories"""
        ancestors = []
        current = self.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors
```

---

## 4. **Time-Based Scheduling & Constraints** ⭐⭐

### What We Can Borrow from Timetable App

**Period Management:**
- Named periods with order
- Start/end times
- Active/inactive status

**Conflict Prevention:**
- `unique_together` on (offering, weekday, period)
- Prevents double-booking
- Room allocation tracking

**Implementation Ideas:**
- Add to exam scheduling
- Meeting room booking
- Teacher availability tracking
- Facility scheduling

```python
class TimeSlot(models.Model):
    """Reusable time slot for various scheduling needs"""
    name = models.CharField(max_length=64)
    day_of_week = models.CharField(max_length=3, choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    def conflicts_with(self, other_slot):
        """Check if this slot conflicts with another"""
        if self.day_of_week != other_slot.day_of_week:
            return False
        return (self.start_time < other_slot.end_time and 
                self.end_time > other_slot.start_time)
```

---

## 5. **Audience Targeting & Notifications** ⭐⭐

### What We Can Borrow from Announcements App

**Audience Segmentation:**
- `ALL`, `TEACHERS`, `STUDENTS`, `PARENTS`
- Targeted messaging
- Role-based filtering

**Implementation Ideas:**
```python
class Notification(models.Model):
    """Generic notification system"""
    AUDIENCE_CHOICES = (
        ('ALL', 'All'),
        ('ADMIN', 'Administrators'),
        ('CAMPUS_ADMIN', 'Campus Admins'),
        ('TEACHERS', 'Teachers'),
        ('STUDENTS', 'Students'),
        ('PARENTS', 'Parents'),
        ('STAFF', 'Staff'),
    )
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    audience = models.CharField(max_length=16, choices=AUDIENCE_CHOICES)
    campus = models.ForeignKey('Campus', null=True, blank=True)  # Campus-specific
    priority = models.CharField(max_length=16, default='NORMAL')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
```

**Use Cases:**
- System notifications
- Important announcements
- Deadline reminders
- Event notifications

---

## 6. **HR & Department Structure** ⭐⭐

### What We Can Borrow from HR App

**Organizational Structure:**
- `Department` with campus FK
- `Position` linked to departments
- `StaffProfile` separate from teachers
- Campus-specific departments

**Implementation Ideas:**
- Extend to all staff types
- Add reporting structure
- Department budgets
- Staff assignments

```python
class OrganizationalUnit(models.Model):
    """Generic org structure"""
    campus = models.ForeignKey('Campus', on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    parent = models.ForeignKey('self', null=True, blank=True)
    head = models.ForeignKey(User, null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True)
```

---

## 7. **Unique Constraints & Data Integrity** ⭐⭐⭐

### Patterns to Borrow

**From Multiple Apps:**

1. **Conditional Unique Constraints** (Inventory):
```python
constraints = [
    models.UniqueConstraint(
        fields=["sku"],
        condition=~models.Q(sku=""),
        name="uniq_inventory_sku_nonblank",
    )
]
```

2. **Status-Based Constraints** (Hostels):
```python
constraints = [
    models.UniqueConstraint(
        fields=["bed"],
        condition=models.Q(status="ACTIVE"),
        name="uniq_active_bed_allocation",
    )
]
```

3. **Multi-Field Unique Together** (HR):
```python
unique_together = (("campus", "name"),)
```

**Implementation Ideas:**
- Prevent duplicate active enrollments
- Ensure unique codes per campus
- One active assignment per resource

---

## 8. **Related Actions & Activity Tracking** ⭐⭐

### What We Can Borrow from Discipline App

**Action Tracking Pattern:**
```python
class IncidentAction(models.Model):
    incident = models.ForeignKey(Incident, related_name="actions")
    action = models.CharField(max_length=200)
    note = models.TextField(blank=True)
    performed_by_user = models.ForeignKey(User, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Use Cases:**
- Track actions on invoices (payment, reminder sent, etc.)
- Track actions on applications (reviewed, contacted, etc.)
- Track actions on incidents
- Audit trail for important records

---

## 9. **Code/SKU Management** ⭐

### Pattern from Multiple Apps

**Consistent Code Fields:**
- Optional code field with unique constraint
- Display format: `code - name` or just `name`
- Useful for:
  - Inventory items (SKU)
  - Courses (course code)
  - Rooms (room code)
  - Routes (route code)

```python
def __str__(self) -> str:
    return f"{self.code} - {self.name}" if self.code else self.name
```

---

## 10. **Date Range & Validity Periods** ⭐⭐

### Pattern from Multiple Apps

**Start/End Date Pattern:**
- `start_date` and `end_date` fields
- `is_active` boolean for current status
- Useful for:
  - Assignments (transport, hostel)
  - Memberships
  - Subscriptions
  - Access periods

```python
def is_currently_active(self):
    """Check if active based on dates"""
    today = date.today()
    if not self.is_active:
        return False
    if self.start_date and today < self.start_date:
        return False
    if self.end_date and today > self.end_date:
        return False
    return True
```

---

## Priority Implementation Recommendations

### High Priority ⭐⭐⭐

1. **Status History/Audit Trail**
   - Track all status changes
   - Who changed what and when
   - Compliance and accountability

2. **Inventory Management**
   - Stock tracking for resources
   - Asset assignment system
   - Movement history

3. **Unique Constraints Enhancement**
   - Add conditional constraints
   - Prevent data integrity issues
   - Better validation

### Medium Priority ⭐⭐

4. **Notification System**
   - In-app notifications
   - Audience targeting
   - Priority levels

5. **Action Tracking**
   - Related actions on records
   - Activity timeline
   - Audit trail

6. **Time-Based Scheduling**
   - Reusable time slots
   - Conflict detection
   - Resource booking

### Nice to Have ⭐

7. **Hierarchical Resources**
   - Generic tree structure
   - Category management
   - Nested resources

8. **Department Structure**
   - Organizational hierarchy
   - Reporting structure
   - Budget tracking

---

## Implementation Roadmap

### Phase 1: Data Integrity (Week 1)
- [ ] Add conditional unique constraints
- [ ] Implement status-based constraints
- [ ] Add validation helpers

### Phase 2: Audit & Tracking (Week 2)
- [ ] Create StatusHistory model
- [ ] Implement action tracking
- [ ] Add change logging

### Phase 3: Inventory (Week 3)
- [ ] Create stock movement system
- [ ] Add asset assignment
- [ ] Implement stock calculations

### Phase 4: Notifications (Week 4)
- [ ] Build notification model
- [ ] Add audience targeting
- [ ] Create notification center UI

### Phase 5: Scheduling (Week 5)
- [ ] Create time slot system
- [ ] Add conflict detection
- [ ] Implement booking system

---

## Code Examples Ready to Use

### 1. Generic Status History
```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class StatusHistory(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    old_status = models.CharField(max_length=32, blank=True)
    new_status = models.CharField(max_length=32)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
        ]
```

### 2. Stock Movement System
```python
class StockMovement(models.Model):
    IN = 'IN'
    OUT = 'OUT'
    ADJUST = 'ADJUST'
    
    MOVEMENT_CHOICES = (
        (IN, 'Stock In'),
        (OUT, 'Stock Out'),
        (ADJUST, 'Adjustment'),
    )
    
    item = models.ForeignKey('InventoryItem', on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=16, choices=MOVEMENT_CHOICES)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=128, blank=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### 3. Notification System
```python
class Notification(models.Model):
    NORMAL = 'NORMAL'
    URGENT = 'URGENT'
    CRITICAL = 'CRITICAL'
    
    PRIORITY_CHOICES = (
        (NORMAL, 'Normal'),
        (URGENT, 'Urgent'),
        (CRITICAL, 'Critical'),
    )
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=NORMAL)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ('-created_at',)
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
        ]
```

---

## Summary

The existing apps provide excellent patterns for:
1. ✅ Workflow management with status tracking
2. ✅ Inventory and stock control
3. ✅ Hierarchical resource organization
4. ✅ Time-based scheduling
5. ✅ Audience-targeted communications
6. ✅ Data integrity with smart constraints
7. ✅ Activity and action tracking
8. ✅ Date range validations

**Next Steps:**
1. Review and prioritize features
2. Start with high-impact items (audit trail, inventory)
3. Implement incrementally
4. Test thoroughly
5. Document for team

These patterns will significantly enhance system maturity and user experience!
