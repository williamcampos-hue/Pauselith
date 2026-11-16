#requires -Version 5.1
[CmdletBinding()]
param(
 [ValidateSet('Fast','Full')][string]$Suite='Fast',
 [string]$DependenciesFrom,
 [string]$TestOutput,
 [switch]$CheckOnly,
 [switch]$SelfTestFailure
)
$ErrorActionPreference='Stop'
$PSNativeCommandUseErrorActionPreference=$false
$repoRoot=Split-Path $PSScriptRoot -Parent
$runRoot=$null
$exitCode=2
$environmentBefore=@{}
function FullPath([string]$path){
 if(-not [IO.Path]::IsPathRooted($path)){$path=Join-Path $PWD.Path $path}
 return [IO.Path]::GetFullPath($path).TrimEnd('\')
}
function Under([string]$path,[string]$root){
 return $path.Equals($root,[StringComparison]::OrdinalIgnoreCase) -or $path.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)
}
try {
 if($CheckOnly -and $SelfTestFailure){throw 'CheckOnly and SelfTestFailure are mutually exclusive'}
 if(-not $DependenciesFrom){$DependenciesFrom=Join-Path $repoRoot '..\KiyoCut-build'}
 if(-not $TestOutput){$TestOutput=Join-Path $repoRoot '..\KiyoCut-Archivo\Pruebas\Ejecuciones'}
 $dependencies=FullPath $DependenciesFrom
 $output=FullPath $TestOutput
 if($output -eq [IO.Path]::GetPathRoot($output).TrimEnd('\')){throw 'A drive root cannot be TestOutput'}
 if((Under $output $repoRoot) -or (Under $output $dependencies)){throw 'TestOutput must be outside source and dependency directories'}
 $ancestor=$output
 while($ancestor){
  if((Test-Path -LiteralPath (Join-Path $ancestor 'KiyoCut.exe')) -or (Test-Path -LiteralPath (Join-Path $ancestor '.git'))){throw 'TestOutput cannot be inside a KiyoCut installation or repository'}
  $ancestor=[IO.Path]::GetDirectoryName($ancestor)
 }
 New-Item -ItemType Directory -Path $output -Force | Out-Null
 $runLabel=if($SelfTestFailure){'ControlledFailure'}elseif($CheckOnly){$Suite+'-check'}else{$Suite}
 # Compact unique IDs leave room for bundled NumPy license paths on legacy MAX_PATH hosts.
 $runRoot=Join-Path $output ($runLabel+'-'+[DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,12))
 New-Item -ItemType Directory -Path $runRoot | Out-Null
 $python=Join-Path $dependencies 'runtime\python\python.exe'
 if(-not(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Missing bundled Python. Build KiyoCut first or pass -DependenciesFrom pointing to a UC-002A build.'}
 $testEnvironment=@{OPENBLAS_NUM_THREADS='1';OMP_NUM_THREADS='1';PYTHONIOENCODING='utf-8';PYTHONDONTWRITEBYTECODE='1'}
 foreach($key in $testEnvironment.Keys){
  $environmentBefore[$key]=[Environment]::GetEnvironmentVariable($key,'Process')
  [Environment]::SetEnvironmentVariable($key,$testEnvironment[$key],'Process')
 }
 $runnerArgs=@('-I','-B','-X','utf8',(Join-Path $repoRoot 'tests\run_suites.py'),'--suite',$Suite,'--output',$runRoot,'--dependencies',$dependencies)
 if($CheckOnly){$runnerArgs+='--check-only'}
 if($SelfTestFailure){$runnerArgs+='--self-test-failure'}
 & $python @runnerArgs 2>&1 | Tee-Object -FilePath (Join-Path $runRoot 'runner.log')
 $exitCode=$LASTEXITCODE
 if(-not(Test-Path -LiteralPath (Join-Path $runRoot 'summary.json'))){
  throw "Test runner ended without summary.json (exit $exitCode); see runner.log"
 }
} catch {
 $message=$_.Exception.Message
 Write-Host ("ERROR: "+$message) -ForegroundColor Red
 if($runRoot){
  $summary=@{status='configuration_error';message=$message;selected=0;passed=0;failed=0;errors=1;skipped=0;exit_code=2}
  $summary | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runRoot 'summary.json') -Encoding utf8
  Add-Content -LiteralPath (Join-Path $runRoot 'runner.log') -Value ("ERROR: "+$message) -Encoding utf8
 }
 $exitCode=2
} finally {
 foreach($key in $environmentBefore.Keys){[Environment]::SetEnvironmentVariable($key,$environmentBefore[$key],'Process')}
 if($runRoot){Write-Host ("Results: "+$runRoot)}
}
exit $exitCode
