// Static enum-style filter options only -- real entity lists (business
// units, departments, clients, managers, recruiters) are fetched live
// from the API in FilterDrawers.js, not hardcoded here. This file used
// to also export a fake `mockData` job array and fake entity option
// lists (real names like "Riya"/"PRISM" that don't correspond to any
// actual person/client) -- removed 2026-07-23, see FilterDrawers.js.

export const statusOptions = [
    { label: 'Open', value: 'Open' },
    { label: 'Closed', value: 'Closed' },
    { label: 'Lean', value: 'Lean' }
  ];

  export const jobTypeOptions = [
    { label: 'Internal', value: 'Internal' },
    { label: 'External', value: 'External' }
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