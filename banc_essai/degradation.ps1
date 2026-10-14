#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

function Degrader-Nom {
    $nouveauNom = 'DESKTOP-K4N2P1'
    Write-Host "Dégradation 1 : la machine va être renommée $nouveauNom (effet après redémarrage)."
    Rename-Computer -NewName $nouveauNom -Force
    Write-Host "Dégradation 1 : terminée."
}

function Degrader-IP {
    Write-Host "Dégradation 2 : adresse IP fixe 10.0.2.15 (DHCP désactivé)."
    Set-NetIPInterface -InterfaceAlias 'Ethernet' -Dhcp Disabled
    Remove-NetIPAddress -InterfaceAlias 'Ethernet' -AddressFamily IPv4 -Confirm:$false
    New-NetIPAddress -InterfaceAlias 'Ethernet' -IPAddress 10.0.2.15 -PrefixLength 24 -DefaultGateway 10.0.2.2 | Out-Null
    Set-DnsClientServerAddress -InterfaceAlias 'Ethernet' -ServerAddresses ('1.1.1.1','8.8.8.8')
    Write-Host "Dégradation 2 : terminée."
}

function Degrader-Imprimante {
    Write-Host "Dégradation 5 : suppression de l'imprimante Imprimante-Comptabilite."
    Remove-Printer -Name 'Imprimante-Comptabilite'
    Write-Host "Dégradation 5 : terminée."
}

function Degrader-LogicielInterdit {
    Write-Host "Dégradation 7 : installation de qBittorrent (logiciel interdit)."
    winget install --id qBittorrent.qBittorrent -e --silent --accept-package-agreements --accept-source-agreements
    Write-Host "Dégradation 7 : terminée (à vérifier dans le registre)."
}

function Degrader-Environnement {
    Write-Host "Dégradation 9 : pavé numérique, explorateur et Chrome remis par défaut."
    Set-ItemProperty -Path 'HKCU:\Control Panel\Keyboard' -Name 'InitialKeyboardIndicators' -Value '0'
    $adv = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
    Set-ItemProperty -Path $adv -Name 'HideFileExt' -Value 1 -Type DWord
    Set-ItemProperty -Path $adv -Name 'Hidden' -Value 2 -Type DWord
    Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer' -Name 'ConfirmFileDelete' -Value 0 -Type DWord
    Remove-Item -Path 'HKLM:\SOFTWARE\Policies\Google\Chrome' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Dégradation 9 : terminée."
}

# Degrader-IP
Degrader-Imprimante
Degrader-LogicielInterdit
Degrader-Environnement
# Degrader-Nom