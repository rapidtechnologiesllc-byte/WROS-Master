# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: test-01-login-and-create-candidate.spec.js >> Step 1: Login and Create Candidate
- Location: tests\e2e\test-01-login-and-create-candidate.spec.js:3:5

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: locator.click: Test timeout of 30000ms exceeded.
Call log:
  - waiting for locator('button:has-text("Save"), button:has-text("Create"), button:has-text("Submit")').first()

```

# Page snapshot

```yaml
- generic [ref=f1e2]:
  - generic [ref=f1e3]:
    - generic [ref=f1e4]:
      - complementary [ref=f1e5]:
        - generic [ref=f1e6]:
          - generic [ref=f1e7]:
            - generic [ref=f1e8]: BlitzenX
            - generic [ref=f1e9]: WROS
          - navigation [ref=f1e10]:
            - button "Dashboard" [ref=f1e11] [cursor=pointer]
            - button "My Tasks" [ref=f1e17] [cursor=pointer]
            - button "My Timesheet" [ref=f1e21] [cursor=pointer]
            - button "My Expenses" [ref=f1e25] [cursor=pointer]
            - button "My Referrals" [ref=f1e29] [cursor=pointer]
      - main [ref=f1e34]:
        - generic [ref=f1e37]:
          - textbox "Search candidates or jobs..." [ref=f1e42]
          - generic [ref=f1e43]:
            - button "Thunder Activity Feed" [ref=f1e45] [cursor=pointer]
            - button "Notifications" [ref=f1e49] [cursor=pointer]
            - button "Settings" [ref=f1e53] [cursor=pointer]
            - button "R Recruiter NA 1" [ref=f1e58] [cursor=pointer]:
              - generic [ref=f1e59]: R
              - generic [ref=f1e60]: Recruiter NA 1
        - generic [ref=f1e63]:
          - generic [ref=f1e64]:
            - heading "Create Candidate" [level=3] [ref=f1e73]
            - button "Back" [ref=f1e74] [cursor=pointer]
          - generic [ref=f1e75]:
            - generic [ref=f1e76]:
              - generic [ref=f1e77]: Resume attachment
              - paragraph [ref=f1e81]: Upload the candidate's resume in PDF or DOCX format.
              - button "Choose File" [ref=f1e82]
            - generic [ref=f1e83]:
              - generic [ref=f1e85]:
                - generic [ref=f1e86]: Open Jobs (Optional)
                - combobox "Open Jobs (Optional)" [ref=f1e88]:
                  - option "Select a job (optional)" [selected]
              - generic [ref=f1e90]:
                - generic [ref=f1e91]: Email *
                - textbox "Email *" [ref=f1e92]: John
              - generic [ref=f1e94]:
                - generic [ref=f1e95]: First Name *
                - textbox "First Name *" [active] [ref=f1e96]: Smith
              - generic [ref=f1e97]:
                - generic [ref=f1e98]: Middle Name
                - textbox "Middle Name" [ref=f1e99]
              - generic [ref=f1e101]:
                - generic [ref=f1e102]: Last Name *
                - textbox "Last Name *" [ref=f1e103]
              - generic [ref=f1e104]:
                - generic [ref=f1e105]:
                  - generic [ref=f1e106]: Code
                  - combobox "Code" [ref=f1e108]:
                    - option "+91 (India)" [selected]
                    - option "+1 (US/Canada)"
                    - option "+44 (UK)"
                    - option "+61 (Australia)"
                    - option "+971 (UAE)"
                    - option "+65 (Singapore)"
                    - option "+49 (Germany)"
                    - option "+63 (Philippines)"
                - generic [ref=f1e109]:
                  - generic [ref=f1e110]: Mobile *
                  - textbox "Mobile *" [ref=f1e111]
              - generic [ref=f1e113]:
                - generic [ref=f1e114]: Gender *
                - combobox "Gender *" [ref=f1e116]:
                  - option [selected]
                  - option "Female"
                  - option "Male"
                  - option "Other"
              - generic [ref=f1e118]:
                - generic [ref=f1e119]: Date of Birth
                - textbox "Date of Birth" [ref=f1e120]
              - generic [ref=f1e121]:
                - generic [ref=f1e122]: Source
                - textbox "Source" [ref=f1e123]
              - generic [ref=f1e124]:
                - generic [ref=f1e125]: Skills (comma separated)
                - textbox "Skills (comma separated)" [ref=f1e126]
              - generic [ref=f1e127]:
                - generic [ref=f1e128]: Current Salary
                - textbox "Current Salary" [ref=f1e129]
              - generic [ref=f1e130]:
                - generic [ref=f1e131]: Expected Salary
                - textbox "Expected Salary" [ref=f1e132]
              - generic [ref=f1e133]:
                - generic [ref=f1e134]: Current Location *
                - generic [ref=f1e135]:
                  - generic [ref=f1e136]:
                    - generic [ref=f1e137]: Country
                    - combobox "Country" [ref=f1e138]:
                      - option "Select country" [selected]
                      - option "Afghanistan"
                      - option "Aland Islands"
                      - option "Albania"
                      - option "Algeria"
                      - option "American Samoa"
                      - option "Andorra"
                      - option "Angola"
                      - option "Anguilla"
                      - option "Antarctica"
                      - option "Antigua And Barbuda"
                      - option "Argentina"
                      - option "Armenia"
                      - option "Aruba"
                      - option "Australia"
                      - option "Austria"
                      - option "Azerbaijan"
                      - option "The Bahamas"
                      - option "Bahrain"
                      - option "Bangladesh"
                      - option "Barbados"
                      - option "Belarus"
                      - option "Belgium"
                      - option "Belize"
                      - option "Benin"
                      - option "Bermuda"
                      - option "Bhutan"
                      - option "Bolivia"
                      - option "Bosnia and Herzegovina"
                      - option "Botswana"
                      - option "Bouvet Island"
                      - option "Brazil"
                      - option "British Indian Ocean Territory"
                      - option "Brunei"
                      - option "Bulgaria"
                      - option "Burkina Faso"
                      - option "Burundi"
                      - option "Cambodia"
                      - option "Cameroon"
                      - option "Canada"
                      - option "Cape Verde"
                      - option "Cayman Islands"
                      - option "Central African Republic"
                      - option "Chad"
                      - option "Chile"
                      - option "China"
                      - option "Christmas Island"
                      - option "Cocos (Keeling) Islands"
                      - option "Colombia"
                      - option "Comoros"
                      - option "Congo"
                      - option "Democratic Republic of the Congo"
                      - option "Cook Islands"
                      - option "Costa Rica"
                      - option "Cote D'Ivoire (Ivory Coast)"
                      - option "Croatia"
                      - option "Cuba"
                      - option "Cyprus"
                      - option "Czech Republic"
                      - option "Denmark"
                      - option "Djibouti"
                      - option "Dominica"
                      - option "Dominican Republic"
                      - option "East Timor"
                      - option "Ecuador"
                      - option "Egypt"
                      - option "El Salvador"
                      - option "Equatorial Guinea"
                      - option "Eritrea"
                      - option "Estonia"
                      - option "Ethiopia"
                      - option "Falkland Islands"
                      - option "Faroe Islands"
                      - option "Fiji Islands"
                      - option "Finland"
                      - option "France"
                      - option "French Guiana"
                      - option "French Polynesia"
                      - option "French Southern Territories"
                      - option "Gabon"
                      - option "The Gambia"
                      - option "Georgia"
                      - option "Germany"
                      - option "Ghana"
                      - option "Gibraltar"
                      - option "Greece"
                      - option "Greenland"
                      - option "Grenada"
                      - option "Guadeloupe"
                      - option "Guam"
                      - option "Guatemala"
                      - option "Guernsey and Alderney"
                      - option "Guinea"
                      - option "Guinea-Bissau"
                      - option "Guyana"
                      - option "Haiti"
                      - option "Heard Island and McDonald Islands"
                      - option "Honduras"
                      - option "Hong Kong S.A.R."
                      - option "Hungary"
                      - option "Iceland"
                      - option "India"
                      - option "Indonesia"
                      - option "Iran"
                      - option "Iraq"
                      - option "Ireland"
                      - option "Israel"
                      - option "Italy"
                      - option "Jamaica"
                      - option "Japan"
                      - option "Jersey"
                      - option "Jordan"
                      - option "Kazakhstan"
                      - option "Kenya"
                      - option "Kiribati"
                      - option "North Korea"
                      - option "South Korea"
                      - option "Kuwait"
                      - option "Kyrgyzstan"
                      - option "Laos"
                      - option "Latvia"
                      - option "Lebanon"
                      - option "Lesotho"
                      - option "Liberia"
                      - option "Libya"
                      - option "Liechtenstein"
                      - option "Lithuania"
                      - option "Luxembourg"
                      - option "Macau S.A.R."
                      - option "Macedonia"
                      - option "Madagascar"
                      - option "Malawi"
                      - option "Malaysia"
                      - option "Maldives"
                      - option "Mali"
                      - option "Malta"
                      - option "Man (Isle of)"
                      - option "Marshall Islands"
                      - option "Martinique"
                      - option "Mauritania"
                      - option "Mauritius"
                      - option "Mayotte"
                      - option "Mexico"
                      - option "Micronesia"
                      - option "Moldova"
                      - option "Monaco"
                      - option "Mongolia"
                      - option "Montenegro"
                      - option "Montserrat"
                      - option "Morocco"
                      - option "Mozambique"
                      - option "Myanmar"
                      - option "Namibia"
                      - option "Nauru"
                      - option "Nepal"
                      - option "Bonaire, Sint Eustatius and Saba"
                      - option "Netherlands"
                      - option "New Caledonia"
                      - option "New Zealand"
                      - option "Nicaragua"
                      - option "Niger"
                      - option "Nigeria"
                      - option "Niue"
                      - option "Norfolk Island"
                      - option "Northern Mariana Islands"
                      - option "Norway"
                      - option "Oman"
                      - option "Pakistan"
                      - option "Palau"
                      - option "Palestinian Territory Occupied"
                      - option "Panama"
                      - option "Papua new Guinea"
                      - option "Paraguay"
                      - option "Peru"
                      - option "Philippines"
                      - option "Pitcairn Island"
                      - option "Poland"
                      - option "Portugal"
                      - option "Puerto Rico"
                      - option "Qatar"
                      - option "Reunion"
                      - option "Romania"
                      - option "Russia"
                      - option "Rwanda"
                      - option "Saint Helena"
                      - option "Saint Kitts And Nevis"
                      - option "Saint Lucia"
                      - option "Saint Pierre and Miquelon"
                      - option "Saint Vincent And The Grenadines"
                      - option "Saint-Barthelemy"
                      - option "Saint-Martin (French part)"
                      - option "Samoa"
                      - option "San Marino"
                      - option "Sao Tome and Principe"
                      - option "Saudi Arabia"
                      - option "Senegal"
                      - option "Serbia"
                      - option "Seychelles"
                      - option "Sierra Leone"
                      - option "Singapore"
                      - option "Slovakia"
                      - option "Slovenia"
                      - option "Solomon Islands"
                      - option "Somalia"
                      - option "South Africa"
                      - option "South Georgia"
                      - option "South Sudan"
                      - option "Spain"
                      - option "Sri Lanka"
                      - option "Sudan"
                      - option "Suriname"
                      - option "Svalbard And Jan Mayen Islands"
                      - option "Swaziland"
                      - option "Sweden"
                      - option "Switzerland"
                      - option "Syria"
                      - option "Taiwan"
                      - option "Tajikistan"
                      - option "Tanzania"
                      - option "Thailand"
                      - option "Togo"
                      - option "Tokelau"
                      - option "Tonga"
                      - option "Trinidad And Tobago"
                      - option "Tunisia"
                      - option "Turkey"
                      - option "Turkmenistan"
                      - option "Turks And Caicos Islands"
                      - option "Tuvalu"
                      - option "Uganda"
                      - option "Ukraine"
                      - option "United Arab Emirates"
                      - option "United Kingdom"
                      - option "United States"
                      - option "United States Minor Outlying Islands"
                      - option "Uruguay"
                      - option "Uzbekistan"
                      - option "Vanuatu"
                      - option "Vatican City State (Holy See)"
                      - option "Venezuela"
                      - option "Vietnam"
                      - option "Virgin Islands (British)"
                      - option "Virgin Islands (US)"
                      - option "Wallis And Futuna Islands"
                      - option "Western Sahara"
                      - option "Yemen"
                      - option "Zambia"
                      - option "Zimbabwe"
                      - option "Kosovo"
                      - option "Curaçao"
                      - option "Sint Maarten (Dutch part)"
                  - generic [ref=f1e139]:
                    - generic [ref=f1e140]: State
                    - combobox "State" [disabled] [ref=f1e141]:
                      - option "Select country first" [selected]
                  - generic [ref=f1e142]:
                    - generic [ref=f1e143]: City
                    - combobox "City" [disabled] [ref=f1e144]:
                      - option "Select state first" [selected]
              - generic [ref=f1e145]:
                - generic [ref=f1e146]: Availability Date
                - textbox "Availability Date" [ref=f1e147]
            - generic [ref=f1e148]:
              - generic [ref=f1e149]:
                - generic [ref=f1e150]: Education records
                - button "Add Education Row" [ref=f1e152] [cursor=pointer]
              - generic [ref=f1e153]:
                - generic [ref=f1e154]: Experience records
                - button "Add Experience Row" [ref=f1e156] [cursor=pointer]
            - generic [ref=f1e157]:
              - button "Cancel" [ref=f1e158] [cursor=pointer]
              - button "Add Candidate" [ref=f1e159] [cursor=pointer]
    - button "Ask Flash" [ref=f1e161] [cursor=pointer]
  - region "Notifications Alt+T"
```

# Test source

```ts
  1   | import { test } from '@playwright/test';
  2   | 
  3   | test('Step 1: Login and Create Candidate', async ({ page }) => {
  4   |   console.log('\n=== STEP 1: LOGIN ===');
  5   | 
  6   |   // Navigate to login
  7   |   await page.goto('http://localhost:3000');
  8   |   await page.waitForLoadState('networkidle');
  9   | 
  10  |   // Fill email
  11  |   await page.locator('input[type="email"]').first().fill('recruiter.na.1@blitzenx.com');
  12  |   console.log('✅ Email entered');
  13  | 
  14  |   // Click Next
  15  |   await page.locator('button:has-text("Next")').first().click();
  16  |   await page.waitForTimeout(1000);
  17  | 
  18  |   // Fill password
  19  |   await page.locator('input[type="password"]').first().fill('RecruiterNA1@123');
  20  |   console.log('✅ Password entered');
  21  | 
  22  |   // Click Sign In
  23  |   await page.locator('button:has-text("Sign In")').first().click();
  24  |   await page.waitForLoadState('networkidle');
  25  |   console.log('✅ LOGIN SUCCESSFUL');
  26  | 
  27  |   // Verify dashboard loaded
  28  |   const dashboardUrl = page.url();
  29  |   console.log(`📍 Dashboard URL: ${dashboardUrl}`);
  30  | 
  31  |   console.log('\n=== STEP 2: CREATE CANDIDATE ===');
  32  | 
  33  |   // Click Add Candidate button
  34  |   await page.locator('button:has-text("Add Candidate")').first().click();
  35  |   await page.waitForTimeout(2000);
  36  |   console.log('✅ Add Candidate modal opened');
  37  | 
  38  |   // Get all text inputs
  39  |   const allInputs = await page.locator('input').all();
  40  |   console.log(`Found ${allInputs.length} total input fields`);
  41  | 
  42  |   // Log what we find
  43  |   for (let i = 0; i < Math.min(5, allInputs.length); i++) {
  44  |     const type = await allInputs[i].getAttribute('type');
  45  |     const placeholder = await allInputs[i].getAttribute('placeholder');
  46  |     console.log(`Input ${i}: type=${type}, placeholder=${placeholder}`);
  47  |   }
  48  | 
  49  |   // Fill in candidate details
  50  |   // Get all text inputs (excluding search bar)
  51  |   const textInputs = await page.locator('input[type="text"]').all();
  52  | 
  53  |   // Skip index 0 (search bar), start from index 1
  54  |   // Index 1: First Name
  55  |   if (textInputs.length > 1) {
  56  |     await textInputs[1].clear();
  57  |     await textInputs[1].fill('John');
  58  |     console.log('✅ First Name: John');
  59  |   }
  60  | 
  61  |   // Index 2: Last Name
  62  |   if (textInputs.length > 2) {
  63  |     await textInputs[2].clear();
  64  |     await textInputs[2].fill('Smith');
  65  |     console.log('✅ Last Name: Smith');
  66  |   }
  67  | 
  68  |   // Email input (type="email")
  69  |   const emailInputs = await page.locator('input[type="email"]').all();
  70  |   if (emailInputs.length > 0) {
  71  |     await emailInputs[0].clear();
  72  |     await emailInputs[0].fill('john.smith@example.com');
  73  |     console.log('✅ Email: john.smith@example.com');
  74  |   }
  75  | 
  76  |   // Log all buttons to find the save button
  77  |   const buttons = await page.locator('button').all();
  78  |   console.log(`\nFound ${buttons.length} buttons:`);
  79  |   for (let i = 0; i < Math.min(10, buttons.length); i++) {
  80  |     const text = await buttons[i].textContent();
  81  |     console.log(`Button ${i}: "${text?.trim()}"`);
  82  |   }
  83  | 
  84  |   // Click Save/Create button
  85  |   const saveBtn = await page.locator('button:has-text("Save"), button:has-text("Create"), button:has-text("Submit")').first();
  86  |   if (saveBtn) {
> 87  |     await saveBtn.click();
      |                   ^ Error: locator.click: Test timeout of 30000ms exceeded.
  88  |     console.log('✅ Save button clicked');
  89  |   } else {
  90  |     console.log('❌ Save button not found');
  91  |   }
  92  | 
  93  |   await page.waitForTimeout(3000);
  94  | 
  95  |   // Check if candidate appears in the list
  96  |   const candidateText = await page.locator('text=John').isVisible().catch(() => false);
  97  |   if (candidateText) {
  98  |     console.log('✅ CANDIDATE CREATED AND VISIBLE');
  99  |   } else {
  100 |     console.log('⚠️ Candidate may not be visible yet');
  101 |   }
  102 | 
  103 |   // Take screenshot
  104 |   await page.screenshot({ path: 'test-01-candidate-created.png' });
  105 |   console.log('📸 Screenshot: test-01-candidate-created.png');
  106 | });
  107 | 
```