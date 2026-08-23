# Frontend Job Title Integration Guide

**Status:** Templates Ready for Implementation  
**Date:** 2026-08-13  

---

## 1. Create User Form Update

**File:** `src/screens/UsersAndAccessControl.js`

### Current State (Before)
```javascript
// Old form with separate Role + Permission Template dropdowns
const [formData, setFormData] = useState({
  user_name: '',
  user_email: '',
  user_password: '',
  role: '', // REMOVE THIS
  permission_template: '', // REMOVE THIS
  business_unit_id: null,
});
```

### Updated State (After)
```javascript
const [formData, setFormData] = useState({
  user_name: '',
  user_email: '',
  user_password: '',
  business_unit_id: null,  // MANDATORY - Step 1
  reporting_manager_id: null,  // MANDATORY - Step 2
  job_title_id: null,  // MANDATORY - Step 3
});

// Helper states
const [selectedBU, setSelectedBU] = useState(null);
const [managers, setManagers] = useState([]);
const [jobTitles, setJobTitles] = useState([]);
```

### Step 1: Business Unit Selector (MANDATORY)
```javascript
const handleBUChange = async (buId) => {
  setSelectedBU(buId);
  setFormData({...formData, business_unit_id: buId});
  
  // Fetch managers for this BU
  try {
    const response = await fetch(
      `/api/managers?business_unit_id=${buId}`,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    const data = await response.json();
    setManagers(data);
  } catch (error) {
    console.error('Failed to fetch managers:', error);
  }
};

return (
  <div className="form-group">
    <label>Business Unit *</label>
    <select 
      value={selectedBU || ''} 
      onChange={(e) => handleBUChange(parseInt(e.target.value))}
      required
    >
      <option value="">-- Select Business Unit --</option>
      {businessUnits.map(bu => (
        <option key={bu.id} value={bu.id}>{bu.name}</option>
      ))}
    </select>
  </div>
);
```

### Step 2: Reporting Manager Selector (Filtered by BU)
```javascript
const handleManagerChange = (managerId) => {
  setFormData({...formData, reporting_manager_id: managerId});
};

return (
  <div className="form-group">
    <label>Reporting Manager *</label>
    <select 
      value={formData.reporting_manager_id || ''}
      onChange={(e) => handleManagerChange(parseInt(e.target.value))}
      disabled={!selectedBU}  // Only enabled if BU selected
      required
    >
      <option value="">-- Select Reporting Manager --</option>
      {managers.map(mgr => (
        <option key={mgr.id} value={mgr.id}>{mgr.user_name}</option>
      ))}
    </select>
  </div>
);
```

### Step 3: Job Title Selector
```javascript
const handleJobTitleChange = (jobTitleId) => {
  setFormData({...formData, job_title_id: jobTitleId});
};

return (
  <div className="form-group">
    <label>Job Title *</label>
    <select 
      value={formData.job_title_id || ''}
      onChange={(e) => handleJobTitleChange(parseInt(e.target.value))}
      required
    >
      <option value="">-- Select Job Title --</option>
      {jobTitles.map(jt => (
        <option key={jt.id} value={jt.id}>{jt.name}</option>
      ))}
    </select>
  </div>
);
```

### Step 4: Submit Handler
```javascript
const handleCreateUser = async (e) => {
  e.preventDefault();
  
  // Validate required fields
  if (!formData.business_unit_id || !formData.reporting_manager_id || !formData.job_title_id) {
    alert('All fields are required');
    return;
  }
  
  try {
    const response = await fetch('/api/users', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        user_name: formData.user_name,
        user_email: formData.user_email,
        user_password: formData.user_password,
        business_unit_id: formData.business_unit_id,  // From Step 1
        reporting_manager_id: formData.reporting_manager_id,  // From Step 2
        job_title_id: formData.job_title_id,  // From Step 3
        // role_ids will be derived from job_title_id on backend
      }),
    });
    
    if (response.ok) {
      const newUser = await response.json();
      alert(`User created: ${newUser.user_name}`);
      // Refresh user list
      loadUsers();
      // Reset form
      setFormData({...initialFormData});
    } else {
      alert(`Error: ${response.statusText}`);
    }
  } catch (error) {
    console.error('Failed to create user:', error);
  }
};
```

---

## 2. Admin Settings: Job Titles Management

**File:** `src/screens/AdminSettingsScreen.js`

### New Tab: Organization → Job Titles

```javascript
const [jobTitles, setJobTitles] = useState([]);
const [showAddJobTitleModal, setShowAddJobTitleModal] = useState(false);
const [newJobTitle, setNewJobTitle] = useState({
  name: '',
  description: '',
  role_ids: []  // Selected roles for this job title
});

// Load job titles on mount
useEffect(() => {
  const loadJobTitles = async () => {
    try {
      const response = await fetch('/api/job-titles', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const data = await response.json();
      setJobTitles(data);
    } catch (error) {
      console.error('Failed to load job titles:', error);
    }
  };
  loadJobTitles();
}, []);

// Add job title
const handleAddJobTitle = async () => {
  if (!newJobTitle.name || newJobTitle.role_ids.length === 0) {
    alert('Job title name and at least one role required');
    return;
  }
  
  try {
    const response = await fetch('/api/job-titles', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      body: JSON.stringify({
        name: newJobTitle.name,
        description: newJobTitle.description,
        role_ids: newJobTitle.role_ids,
        active: true
      }),
    });
    
    if (response.ok) {
      const created = await response.json();
      setJobTitles([...jobTitles, created]);
      setShowAddJobTitleModal(false);
      setNewJobTitle({name: '', description: '', role_ids: []});
      alert('Job title created successfully');
    }
  } catch (error) {
    console.error('Failed to create job title:', error);
  }
};

// Delete job title
const handleDeleteJobTitle = async (jobTitleId) => {
  if (!confirm('Are you sure you want to delete this job title?')) return;
  
  try {
    const response = await fetch(`/api/job-titles/${jobTitleId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` }
    });
    
    if (response.ok) {
      setJobTitles(jobTitles.filter(jt => jt.id !== jobTitleId));
      alert('Job title deleted');
    }
  } catch (error) {
    console.error('Failed to delete job title:', error);
  }
};

// Render job titles table
return (
  <div className="admin-section">
    <h2>Job Titles</h2>
    <button onClick={() => setShowAddJobTitleModal(true)}>
      + Add Job Title
    </button>
    
    <table>
      <thead>
        <tr>
          <th>Title</th>
          <th>Description</th>
          <th>Roles</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {jobTitles.map(jt => (
          <tr key={jt.id}>
            <td>{jt.name}</td>
            <td>{jt.description}</td>
            <td>{jt.roles?.map(r => r.name).join(', ')}</td>
            <td>{jt.active ? 'Active' : 'Inactive'}</td>
            <td>
              <button onClick={() => handleEditJobTitle(jt.id)}>Edit</button>
              <button onClick={() => handleDeleteJobTitle(jt.id)}>Delete</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
    
    {/* Add Job Title Modal */}
    {showAddJobTitleModal && (
      <Modal onClose={() => setShowAddJobTitleModal(false)}>
        <h3>Add Job Title</h3>
        <input 
          type="text" 
          placeholder="Job Title Name" 
          value={newJobTitle.name}
          onChange={(e) => setNewJobTitle({...newJobTitle, name: e.target.value})}
        />
        <textarea 
          placeholder="Description" 
          value={newJobTitle.description}
          onChange={(e) => setNewJobTitle({...newJobTitle, description: e.target.value})}
        />
        <div>
          <label>Roles (select one or more):</label>
          {roles.map(role => (
            <label key={role.id}>
              <input 
                type="checkbox"
                checked={newJobTitle.role_ids.includes(role.id)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setNewJobTitle({
                      ...newJobTitle,
                      role_ids: [...newJobTitle.role_ids, role.id]
                    });
                  } else {
                    setNewJobTitle({
                      ...newJobTitle,
                      role_ids: newJobTitle.role_ids.filter(id => id !== role.id)
                    });
                  }
                }}
              />
              {role.name}
            </label>
          ))}
        </div>
        <button onClick={handleAddJobTitle}>Create Job Title</button>
      </Modal>
    )}
  </div>
);
```

---

## 3. Implementation Checklist

- [ ] Update Create User form: Add BU selector
- [ ] Update Create User form: Add Manager selector (filtered by BU)
- [ ] Update Create User form: Add Job Title selector
- [ ] Update Create User form: Remove old "Permission Template" dropdown
- [ ] Remove old "Role" dropdown (roles derived from job_title_id)
- [ ] Update form submission to pass job_title_id
- [ ] Add Job Titles management section to Admin Settings
- [ ] Add Job Title add/edit/delete functionality
- [ ] Test form with different BUs
- [ ] Test manager dropdown filters by selected BU
- [ ] Test job title dropdown loads and saves correctly
- [ ] Test that creating user creates required relationships
- [ ] Test admin can manage job titles
- [ ] Test that job titles are loaded on page load

---

## 4. API Endpoints Required (Backend)

These endpoints need to exist for the frontend to work:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/managers?business_unit_id={id}` | Get managers for a BU |
| GET | `/api/job-titles` | List all job titles |
| POST | `/api/job-titles` | Create new job title |
| PUT | `/api/job-titles/{id}` | Update job title |
| DELETE | `/api/job-titles/{id}` | Delete job title |
| POST | `/api/users` | Create user (with job_title_id) |

**Status:** Endpoints need to be implemented in backend routes

---

## 5. Testing Checklist

### Unit Tests
- [ ] BU selector loads business units
- [ ] Manager selector only shows managers from selected BU
- [ ] Job title selector loads all available titles
- [ ] Form validates required fields
- [ ] Submit sends correct payload to backend

### Integration Tests
- [ ] Can create user with recruiter job title
- [ ] User gets correct permissions based on job title
- [ ] Can update job titles in admin settings
- [ ] Job title changes affect new users only

### E2E Tests
- [ ] Create recruiter user with North America BU
- [ ] Create job in North America
- [ ] Submit candidate on that job
- [ ] Verify recruiter can see candidate
- [ ] Verify recruiter cannot delete (if permission not granted)

---

## 6. Styling Notes

Match existing form styling in:
- `src/styles/Forms.css`
- `src/styles/Modals.css`
- `src/components/FormFields.js`

Use existing components:
- `<FormField />`
- `<SelectField />`
- `<Modal />`
- `<Button />`

---

**Status:** ✅ Ready for Implementation  
**Next Step:** Integrate into actual UI and test end-to-end

