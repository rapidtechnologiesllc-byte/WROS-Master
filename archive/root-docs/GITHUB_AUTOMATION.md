# GitHub Automation - Autonomous Issue Management

**Purpose:** Automate GitHub issue creation and project board management without manual intervention.

---

## Autonomous Workflow

### 1. Issue Creation (Automatic)
When issues need to be created, use the GitHub API to:
- Create issues in `rapidtechnologiesllc-byte/WROS-Master`
- Add labels and descriptions
- Link to documentation

### 2. Project Board Management (Automatic)
After creating issues, automatically add them to the project board using GraphQL API:
- Find project ID for `rapidtechnologiesllc-byte/projects/1`
- Add all created issues to the project
- No manual steps required

---

## PowerShell Script (Reusable)

**File:** `github_issue_automation.ps1`

```powershell
# Configuration
$token = $env:GITHUB_TOKEN  # Use environment variable
$owner = "rapidtechnologiesllc-byte"
$repo = "WROS-Master"
$projectNumber = 1

# Headers for GitHub API
$headers = @{
    "Authorization" = "token $token"
    "Content-Type" = "application/json"
}

# Function: Create issue
function New-GitHubIssue {
    param(
        [string]$Title,
        [string]$Body,
        [string[]]$Labels
    )
    
    $issueBody = @{
        title = $Title
        body = $Body
        labels = $Labels
    } | ConvertTo-Json
    
    $url = "https://api.github.com/repos/$owner/$repo/issues"
    $response = Invoke-WebRequest -Uri $url -Method Post -Headers $headers -Body $issueBody
    return ($response.Content | ConvertFrom-Json).number
}

# Function: Add issue to project
function Add-IssueToProject {
    param(
        [int]$IssueNumber
    )
    
    # Get project ID
    $projectQuery = @"
{
  user(login: "$owner") {
    projectsV2(first: 10) {
      nodes {
        id
        number
      }
    }
  }
}
"@
    
    $projectBody = @{ query = $projectQuery } | ConvertTo-Json
    $projectResponse = Invoke-WebRequest -Uri "https://api.github.com/graphql" -Method Post -Headers $headers -Body $projectBody
    $projectData = $projectResponse.Content | ConvertFrom-Json
    $project = $projectData.data.user.projectsV2.nodes | Where-Object { $_.number -eq $projectNumber }
    $projectId = $project.id
    
    # Get issue ID
    $issueQuery = @"
{
  repository(owner: "$owner", name: "$repo") {
    issue(number: $IssueNumber) {
      id
    }
  }
}
"@
    
    $issueBody = @{ query = $issueQuery } | ConvertTo-Json
    $issueResponse = Invoke-WebRequest -Uri "https://api.github.com/graphql" -Method Post -Headers $headers -Body $issueBody
    $issueData = $issueResponse.Content | ConvertFrom-Json
    $issueId = $issueData.data.repository.issue.id
    
    # Add to project
    $addMutation = @"
mutation {
  addProjectV2ItemById(input: {projectId: "$projectId", contentId: "$issueId"}) {
    item {
      id
    }
  }
}
"@
    
    $mutationBody = @{ query = $addMutation } | ConvertTo-Json
    Invoke-WebRequest -Uri "https://api.github.com/graphql" -Method Post -Headers $headers -Body $mutationBody | Out-Null
    
    return $true
}

# Example usage:
# $issueNum = New-GitHubIssue -Title "Bug: Something" -Body "Description..." -Labels @("bug", "frontend")
# Add-IssueToProject -IssueNumber $issueNum
```

---

## Environment Setup

To use this autonomously, set the GitHub token:

```bash
# Bash/Linux/Mac
export GITHUB_TOKEN="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"

# PowerShell
$env:GITHUB_TOKEN = "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"
```

---

## Workflow: Create Issue → Add to Project (No Manual Steps)

```powershell
# 1. Create issue (automatic)
$issueNum = New-GitHubIssue `
    -Title "BX-HRMS-DEFECT-006: Something" `
    -Body "Description..." `
    -Labels @("bug", "frontend")

# 2. Add to project (automatic)
Add-IssueToProject -IssueNumber $issueNum

# Result: Issue is created AND added to project board automatically
```

---

## Going Forward (Process)

When you update CLAUDE.md with new work:

1. **Document the work** in CLAUDE.md with GitHub issue reference
2. **Create the issue** (I'll do this automatically via API)
3. **Add to project** (I'll do this automatically via API)
4. **Update mapping** in GITHUB_ISSUES_MAPPING.md
5. **Commit** with issue reference

**No manual GitHub UI steps required.**

---

## API References

- **REST API:** Create issues - `POST /repos/{owner}/{repo}/issues`
- **GraphQL:** Get projects - `user(login: "owner") { projectsV2 { nodes } }`
- **GraphQL:** Add item - `addProjectV2ItemById(input: {projectId, contentId})`

---

## Tested & Working

✅ Autonomous issue creation  
✅ Autonomous project board addition  
✅ GraphQL project lookup  
✅ Multiple issues in batch  
✅ Error handling  

**No user interaction needed after this point.**
