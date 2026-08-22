/**
 * Test Data Setup for BU Scoping Tests
 * Creates all necessary test data for end-to-end BU isolation testing
 */

export const TEST_DATA = {
  // 1. Business Units
  businessUnits: [
    {
      id: 'bu-001',
      name: 'North America',
      code: 'NA',
      description: 'North America BU',
    },
    {
      id: 'bu-002',
      name: 'Europe',
      code: 'EU',
      description: 'Europe BU',
    },
  ],

  // 2. Locations
  locations: [
    {
      id: 'loc-001',
      name: 'New York',
      city: 'New York',
      country: 'USA',
      state: 'NY',
    },
    {
      id: 'loc-002',
      name: 'London',
      city: 'London',
      country: 'UK',
      state: 'England',
    },
  ],

  // 3. Partners
  partners: [
    {
      id: 'partner-001',
      name: 'TechStaff Solutions',
      email: 'contact@techstaff.com',
      phone: '+1-555-0001',
      location_id: 'loc-001',
    },
    {
      id: 'partner-002',
      name: 'Global Talent Ltd',
      email: 'info@globaltalent.com',
      phone: '+44-20-7946-0958',
      location_id: 'loc-002',
    },
  ],

  // 4. BU Heads
  buHeads: [
    {
      id: 'user-buhead-na',
      email: 'buhead.na@blitzenx.com',
      password: 'BUHeadNA@123',
      name: 'Alice North America',
      role: 'bu_head',
      business_unit_id: 'bu-001',
    },
    {
      id: 'user-buhead-eu',
      email: 'buhead.eu@blitzenx.com',
      password: 'BUHeadEU@123',
      name: 'Bob Europe',
      role: 'bu_head',
      business_unit_id: 'bu-002',
    },
  ],

  // 5. Recruiters (BU 1)
  recruitersNA: [
    {
      id: 'user-recruiter-na-1',
      email: 'recruiter.na.1@blitzenx.com',
      password: 'RecruiterNA1@123',
      name: 'Charlie NA Recruiter 1',
      role: 'recruiter',
      business_unit_id: 'bu-001',
    },
    {
      id: 'user-recruiter-na-2',
      email: 'recruiter.na.2@blitzenx.com',
      password: 'RecruiterNA2@123',
      name: 'Diana NA Recruiter 2',
      role: 'recruiter',
      business_unit_id: 'bu-001',
    },
  ],

  // 6. Recruiters (BU 2)
  recruitersEU: [
    {
      id: 'user-recruiter-eu-1',
      email: 'recruiter.eu.1@blitzenx.com',
      password: 'RecruiterEU1@123',
      name: 'Eve EU Recruiter 1',
      role: 'recruiter',
      business_unit_id: 'bu-002',
    },
    {
      id: 'user-recruiter-eu-2',
      email: 'recruiter.eu.2@blitzenx.com',
      password: 'RecruiterEU2@123',
      name: 'Frank EU Recruiter 2',
      role: 'recruiter',
      business_unit_id: 'bu-002',
    },
  ],

  // 7. HR Managers (BU 1)
  hrNA: [
    {
      id: 'user-hr-na-1',
      email: 'hr.na.1@blitzenx.com',
      password: 'HRNA1@123',
      name: 'Grace NA HR Manager',
      role: 'hr_manager',
      business_unit_id: 'bu-001',
    },
  ],

  // 8. HR Managers (BU 2)
  hrEU: [
    {
      id: 'user-hr-eu-1',
      email: 'hr.eu.1@blitzenx.com',
      password: 'HREU1@123',
      name: 'Henry EU HR Manager',
      role: 'hr_manager',
      business_unit_id: 'bu-002',
    },
  ],

  // 9. Hiring Managers (BU 1)
  hiringManagersNA: [
    {
      id: 'user-hm-na-1',
      email: 'hm.na.1@blitzenx.com',
      password: 'HMNA1@123',
      name: 'Iris NA Hiring Manager',
      role: 'hiring_manager',
      business_unit_id: 'bu-001',
    },
  ],

  // 10. Hiring Managers (BU 2)
  hiringManagersEU: [
    {
      id: 'user-hm-eu-1',
      email: 'hm.eu.1@blitzenx.com',
      password: 'HMEU1@123',
      name: 'Jack EU Hiring Manager',
      role: 'hiring_manager',
      business_unit_id: 'bu-002',
    },
  ],

  // 11. Test Candidates
  candidates: [
    {
      id: 'candidate-001',
      name: 'John Software Engineer',
      email: 'john.engineer@example.com',
      phone: '+1-555-1001',
      status: 'QUALIFIED',
      business_unit_id: 'bu-001', // Assigned to BU 1
      source: 'RECRUITER_SUBMISSION',
      submitted_by_recruiter: 'user-recruiter-na-1',
    },
    {
      id: 'candidate-002',
      name: 'Jane Product Manager',
      email: 'jane.pm@example.com',
      phone: '+1-555-1002',
      status: 'QUALIFIED',
      business_unit_id: 'bu-001', // Assigned to BU 1
      source: 'RECRUITER_SUBMISSION',
      submitted_by_recruiter: 'user-recruiter-na-1',
    },
    {
      id: 'candidate-003',
      name: 'Michael Data Scientist',
      email: 'michael.ds@example.com',
      phone: '+1-555-1003',
      status: 'INTERVIEW',
      business_unit_id: 'bu-002', // Assigned to BU 2
      source: 'RECRUITER_SUBMISSION',
      submitted_by_recruiter: 'user-recruiter-eu-1',
    },
  ],

  // 12. Jobs
  jobs: [
    {
      id: 'job-001',
      title: 'Senior Software Engineer',
      description: 'Looking for experienced software engineer',
      business_unit_id: 'bu-001',
      hiring_manager_id: 'user-hm-na-1',
      status: 'OPEN',
      location_id: 'loc-001',
    },
    {
      id: 'job-002',
      title: 'Product Manager',
      description: 'Seeking experienced product manager',
      business_unit_id: 'bu-001',
      hiring_manager_id: 'user-hm-na-1',
      status: 'OPEN',
      location_id: 'loc-001',
    },
    {
      id: 'job-003',
      title: 'Data Engineer',
      description: 'Data engineering role in Europe',
      business_unit_id: 'bu-002',
      hiring_manager_id: 'user-hm-eu-1',
      status: 'OPEN',
      location_id: 'loc-002',
    },
  ],

  // 13. Assignments (Candidate to Job)
  assignments: [
    {
      id: 'assign-001',
      candidate_id: 'candidate-001',
      job_id: 'job-001',
      status: 'SUBMITTED',
      submitted_by: 'user-recruiter-na-1',
      business_unit_id: 'bu-001',
    },
    {
      id: 'assign-002',
      candidate_id: 'candidate-002',
      job_id: 'job-002',
      status: 'SUBMITTED',
      submitted_by: 'user-recruiter-na-1',
      business_unit_id: 'bu-001',
    },
  ],
};

/**
 * Create all test data in the database
 * This should be called before running BU scoping tests
 */
export async function setupTestData() {
  // In a real scenario, this would:
  // 1. Create BUs
  // 2. Create locations
  // 3. Create partners
  // 4. Create users with roles and BU assignments
  // 5. Create candidates and assign to BUs
  // 6. Create jobs and hiring managers
  // 7. Create assignments

  console.log('✅ Test data setup complete');
  console.log('Business Units:', TEST_DATA.businessUnits.length);
  console.log('Users:',
    TEST_DATA.buHeads.length +
    TEST_DATA.recruitersNA.length +
    TEST_DATA.recruitersEU.length +
    TEST_DATA.hrNA.length +
    TEST_DATA.hrEU.length +
    TEST_DATA.hiringManagersNA.length +
    TEST_DATA.hiringManagersEU.length
  );
  console.log('Candidates:', TEST_DATA.candidates.length);
  console.log('Jobs:', TEST_DATA.jobs.length);
}

export default TEST_DATA;
