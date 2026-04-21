const mockData = [
  {
    id: '1023',
    title: 'Azure DevOps Engineer',
    type: 'Internal',
    clientDept: 'PRISM',
    bu: '-',
    location: 'Remote',
    hiringManager: 'Riya',
    recruiter: 2,
    openPositions: 2,
    status: 'Open'
  },
  {
    id: '1024',
    title: 'Azure DevOps Engineer',
    type: 'Internal',
    clientDept: 'PRISM',
    bu: '-',
    location: 'Remote',
    hiringManager: 'Unassigned',
    recruiter: 1,
    openPositions: 1,
    status: 'Lean'
  }
];

export const statusOptions = [
    { label: 'Open', value: 'Open' },
    { label: 'Closed', value: 'Closed' },
    { label: 'Lean', value: 'Lean' }
  ];

  export const jobTypeOptions = [
    { label: 'Internal', value: 'Internal' },
    { label: 'External', value: 'External' }
  ];

  export const buOptions = [
    { label: 'Engineering', value: 'Engineering' },
    { label: 'Sales', value: 'Sales' }
  ];

  export const deptOptions = [
    { label: 'IT', value: 'IT' },
    { label: 'HR', value: 'HR' }
  ];

  export const clientOptions = [
    { label: 'PRISM', value: 'PRISM' },
    { label: 'ABC Corp', value: 'ABC' }
  ];

  export const managerOptions = [
    { label: 'Riya', value: 'Riya' },
    { label: 'A.M', value: 'AM' }
  ];

  export const recruiterOptions = [
    { label: 'John', value: 'John' },
    { label: 'Sara', value: 'Sara' }
  ];

  export const locationOptions = [
    { label: 'Remote', value: 'Remote' },
    { label: 'Onsite', value: 'Onsite' }
  ];

  export const priorityOptions = [
    { label: 'High', value: 'High' },
    { label: 'Medium', value: 'Medium' },
    { label: 'Low', value: 'Low' }
  ];

  export const agingOptions = [
    { label: '0-10 days', value: '0-10' },
    { label: '10-30 days', value: '10-30' },
    { label: '30+ days', value: '30+' }
  ];

export default mockData;