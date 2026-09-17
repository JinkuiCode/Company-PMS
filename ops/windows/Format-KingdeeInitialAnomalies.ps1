param(
    [Parameter(Mandatory = $true)][string]$SourceReport,
    [Parameter(Mandatory = $true)][string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $SourceReport -PathType Leaf)) {
    throw "Source report not found: $SourceReport"
}

$labels = @{
    'DUPLICATE_CODE' = '项目编码重复（分组）'
    'DUPLICATE_CODE_ROW' = '项目编码重复（明细）'
    'DUPLICATE_REMARK' = '拟用项目名称重复（分组）'
    'DUPLICATE_REMARK_ROW' = '拟用项目名称重复（明细）'
    'EXISTING_PMS_CODE' = '与PMS现有项目编码冲突'
    'EXISTING_PMS_NAME' = '与PMS现有项目名称冲突'
    'LEGACY_KINGDEE_NAME' = '金蝶名称与编码不同（提示）'
}
$advice = @{
    'DUPLICATE_CODE' = '核对同编码记录，确定保留哪一条；暂不导入。'
    'DUPLICATE_CODE_ROW' = '与同编码记录一起核对；暂不导入。'
    'DUPLICATE_REMARK' = '核对不同编码是否应共用同一项目名称；暂不导入。'
    'DUPLICATE_REMARK_ROW' = '与同名记录一起核对；暂不导入。'
    'EXISTING_PMS_CODE' = '核对PMS现有档案是否为同一项目；暂不覆盖。'
    'EXISTING_PMS_NAME' = '核对PMS现有档案名称；暂不覆盖。'
    'LEGACY_KINGDEE_NAME' = '仅供核对；PMS名称仍只取金蝶备注，不用金蝶名称替代。'
}

$sourceLines = @(Get-Content -LiteralPath $SourceReport -Encoding UTF8 | Where-Object { $_.Trim() })
$records = @()
$number = 0
foreach ($line in $sourceLines) {
    if ($line -notmatch '^(\S+)\s*(.*)$') { throw "Unrecognized line: $line" }
    $code = $Matches[1]
    $detail = $Matches[2]
    $number++
    $quoted = [regex]::Match($detail, "'([^']*)'")
    $key = if ($quoted.Success) { $quoted.Groups[1].Value } else { ($detail -split '\s+')[0] }
    $category = if ($labels.ContainsKey($code)) { $labels[$code] } else { '其他（请人工核查）' }
    $suggestion = if ($advice.ContainsKey($code)) { $advice[$code] } else { '保留原始信息，人工核查后再决定。' }
    $records += [pscustomobject]@{
        '序号' = $number
        '问题分类' = $category
        '关联项目编码或重复值' = $key
        '原始记录详情' = $detail
        '处理建议' = $suggestion
        '导入处理' = if ($code -eq 'LEGACY_KINGDEE_NAME') { '提示，不阻断' } else { '暂不导入，待确认' }
    }
}

New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
$csvPath = Join-Path $OutputDirectory 'kingdee-initial-anomalies-zh.csv'
$readmePath = Join-Path $OutputDirectory 'kingdee-initial-anomalies-zh.txt'
$originalPath = Join-Path $OutputDirectory 'kingdee-initial-anomalies-original.txt'
$records | Export-Csv -LiteralPath $csvPath -NoTypeInformation -Encoding UTF8
$counts = @{}
foreach ($code in $labels.Keys) {
    $counts[$code] = @($sourceLines | Where-Object { $_ -cmatch "^$code\s" }).Count
}
$notes = @(
    '金蝶项目档案期初导入异常清单'
    '================================'
    '请用 Excel 打开同目录的 kingdee-initial-anomalies-zh.csv。首行为中文标题，每一条原始记录各占一行。'
    '本表仅用于核对，不会修改金蝶或PMS数据库。'
    ''
    "项目编码重复：$($counts['DUPLICATE_CODE']) 组；明细行数：$($counts['DUPLICATE_CODE_ROW'])。"
    "拟用项目名称重复：$($counts['DUPLICATE_REMARK']) 组；明细行数：$($counts['DUPLICATE_REMARK_ROW'])。"
    "与PMS现有编码冲突：$($counts['EXISTING_PMS_CODE']) 条。"
    "与PMS现有名称冲突：$($counts['EXISTING_PMS_NAME']) 条。"
    "金蝶名称与编码不同：$($counts['LEGACY_KINGDEE_NAME']) 条，仅提示，不阻断。"
    ''
    '字段说明：原始记录详情保留旧报告内容，不对末尾数字作未经确认的解释。'
    '映射规则：金蝶项目编码 -> PMS项目编号；金蝶备注 -> PMS项目名称。绝不把金蝶项目名称或编号填作空白备注。'
    '备注为空的记录不属于本异常清单；期初可留空，后续编辑时必须补齐。'
    '旧版原始报告在同目录保留，供逐行复核。'
)
$notes | Set-Content -LiteralPath $readmePath -Encoding UTF8
Copy-Item -LiteralPath $SourceReport -Destination $originalPath -Force
if (@(Import-Csv -LiteralPath $csvPath -Encoding UTF8).Count -ne $sourceLines.Count) {
    throw 'Report row count mismatch'
}
Write-Output "SOURCE_LINES=$($sourceLines.Count) CSV_ROWS=$($records.Count)"
Write-Output "CSV=$csvPath"
Write-Output "README=$readmePath"
