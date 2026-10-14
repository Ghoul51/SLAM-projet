#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

function Degrader-Nom {
    $nouveauNom = 'DESKTOP-K4N2P1'
    Write-Host "Dégradation 1 : la machine va être renommée $nouveauNom (effet après redémarrage)."
    Rename-Computer -NewName $nouveauNom -Force
    Write-Host "Dégradation 1 : terminée."
}

Degrader-Nom