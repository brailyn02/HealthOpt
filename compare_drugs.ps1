$A = Import-Csv 'drugs_cleaned.csv'
$B = Import-Csv 'drugs_cleaned_with_categories.csv'
$a = $A | ForEach-Object { ($_.drug_name -replace '"','').Trim().ToLower() }
$b = $B | ForEach-Object { ($_.drug_name -replace '"','').Trim().ToLower() }
$a_set = $a | Sort-Object -Unique
$b_set = $b | Sort-Object -Unique
$missing = $a_set | Where-Object { $_ -and -not ($b_set -contains $_) }
Write-Output ("A:" + $a_set.Count)
Write-Output ("B:" + $b_set.Count)
Write-Output ("Missing:" + $missing.Count)
$missing | ForEach-Object { Write-Output $_ }
