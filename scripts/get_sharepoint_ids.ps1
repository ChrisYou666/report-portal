param(
    [Parameter(Mandatory = $true)]
    [string]$TenantId,

    [Parameter(Mandatory = $true)]
    [string]$ClientId,

    [Parameter(Mandatory = $true)]
    [string]$ClientSecret,

    [string]$SharePointUrl = "https://julonggroupindonesia.sharepoint.com/sites/report-collection-portal/DocLib/Forms/AllItems.aspx?npsAction=createList"
)

$ErrorActionPreference = "Stop"

function ConvertTo-GraphSitePath {
    param([Uri]$Uri)

    $segments = $Uri.AbsolutePath.Trim("/").Split("/", [System.StringSplitOptions]::RemoveEmptyEntries)
    $sitesIndex = [Array]::IndexOf($segments, "sites")
    if ($sitesIndex -lt 0 -or $segments.Length -lt ($sitesIndex + 2)) {
        throw "Cannot find '/sites/{site-name}' in SharePoint URL: $Uri"
    }

    return "/sites/$($segments[$sitesIndex + 1])"
}

function Get-DocumentLibraryPath {
    param([Uri]$Uri)

    $segments = $Uri.AbsolutePath.Trim("/").Split("/", [System.StringSplitOptions]::RemoveEmptyEntries)
    $formsIndex = [Array]::IndexOf($segments, "Forms")
    if ($formsIndex -gt 1) {
        return $segments[$formsIndex - 1]
    }

    return ""
}

$uri = [Uri]$SharePointUrl
$hostname = $uri.Host
$sitePath = ConvertTo-GraphSitePath -Uri $uri
$libraryPath = Get-DocumentLibraryPath -Uri $uri

Write-Host "SharePoint host: $hostname"
Write-Host "Site path:       $sitePath"
if ($libraryPath) {
    Write-Host "Library path:    $libraryPath"
}
Write-Host ""

$tokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
$tokenBody = @{
    client_id     = $ClientId
    client_secret = $ClientSecret
    scope         = "https://graph.microsoft.com/.default"
    grant_type    = "client_credentials"
}

Write-Host "Getting Microsoft Graph token..."
$tokenResponse = Invoke-RestMethod -Method Post -Uri $tokenUrl -Body $tokenBody
$headers = @{
    Authorization = "Bearer $($tokenResponse.access_token)"
}

$siteApi = "https://graph.microsoft.com/v1.0/sites/$($hostname):$sitePath"
Write-Host "Getting site_id..."
$site = Invoke-RestMethod -Method Get -Uri $siteApi -Headers $headers

Write-Host ""
Write-Host "SITE RESULT"
Write-Host "site_id:     $($site.id)"
Write-Host "displayName: $($site.displayName)"
Write-Host "webUrl:      $($site.webUrl)"

$drivesApi = "https://graph.microsoft.com/v1.0/sites/$($site.id)/drives"
Write-Host ""
Write-Host "Getting document library drive IDs..."
$drives = Invoke-RestMethod -Method Get -Uri $drivesApi -Headers $headers

$rows = $drives.value | Select-Object `
    @{Name = "match"; Expression = {
        if ($libraryPath -and ($_.webUrl -like "*/$libraryPath" -or $_.webUrl -like "*/$libraryPath/*" -or $_.name -eq $libraryPath)) {
            "yes"
        } else {
            ""
        }
    }},
    id,
    name,
    driveType,
    webUrl

Write-Host ""
Write-Host "DRIVE RESULTS"
$rows | Format-Table -AutoSize

$matchedDrive = $rows | Where-Object { $_.match -eq "yes" } | Select-Object -First 1
if ($matchedDrive) {
    Write-Host ""
    Write-Host "LIKELY TARGET DRIVE"
    Write-Host "drive_id: $($matchedDrive.id)"
    Write-Host "name:     $($matchedDrive.name)"
    Write-Host "webUrl:   $($matchedDrive.webUrl)"
}

Write-Host ""
Write-Host "ENV SNIPPET"
Write-Host "ONEDRIVE_TENANT_ID=$TenantId"
Write-Host "ONEDRIVE_CLIENT_ID=$ClientId"
Write-Host "ONEDRIVE_CLIENT_SECRET=<keep-your-secret-in-backend-.env-only>"
Write-Host "ONEDRIVE_DRIVE_ID=<copy drive_id from DRIVE RESULTS>"
Write-Host "ONEDRIVE_ROOT_FOLDER=报表原始文件"
