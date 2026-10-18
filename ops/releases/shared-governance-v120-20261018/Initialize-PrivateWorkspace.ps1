param([switch]$ApprovedWorkspacePreparation,[string]$ApprovalReference)
$ErrorActionPreference='Stop'
if(-not $ApprovedWorkspacePreparation -or $ApprovalReference.Length -lt 8){throw 'Separately approved private workspace preparation required'}
$addresses=@([Net.Dns]::GetHostAddresses([Net.Dns]::GetHostName())|ForEach-Object {$_.IPAddressToString})
if($addresses -notcontains '10.10.1.228'){throw 'Wrong host'}
$target='C:\PMS\.runtime\shared-governance-v120-20261018'
if(Test-Path -LiteralPath $target){throw 'Existing workspace; inspect, do not replace permissions blindly'}
$null=New-Item -ItemType Directory -Path $target
$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User
$acl=New-Object Security.AccessControl.DirectorySecurity
$acl.SetOwner($sid)
$acl.SetAccessRuleProtection($true,$false)
foreach($s in @($sid.Value,'S-1-5-18','S-1-5-32-544')){
    $identity=New-Object Security.Principal.SecurityIdentifier($s)
    $rule=New-Object Security.AccessControl.FileSystemAccessRule($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
    $acl.AddAccessRule($rule)
}
Set-Acl -LiteralPath $target -AclObject $acl
Write-Output 'PRIVATE_WORKSPACE_CREATED_ONLY_NO_SOURCE_OR_SERVICE_CHANGE'
