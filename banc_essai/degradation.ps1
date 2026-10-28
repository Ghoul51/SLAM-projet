#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'

function Degrader-Nom {
    $nouveauNom = 'DESKTOP-K4N2P1'
    Write-Host "Dégradation du nom : la machine va être renommée $nouveauNom (effet après redémarrage)."
    Rename-Computer -NewName $nouveauNom -Force
    Write-Host "Dégradation du nom : terminée."
}

function Degrader-IP {
    Write-Host "Dégradation IP : adresse IP fixe 10.0.2.15 (DHCP désactivé)."
    Set-NetIPInterface -InterfaceAlias 'Ethernet' -Dhcp Disabled
    Remove-NetIPAddress -InterfaceAlias 'Ethernet' -AddressFamily IPv4 -Confirm:$false -ErrorAction SilentlyContinue
    New-NetIPAddress -InterfaceAlias 'Ethernet' -IPAddress 10.0.2.15 -PrefixLength 24 -DefaultGateway 10.0.2.2 | Out-Null
    Set-DnsClientServerAddress -InterfaceAlias 'Ethernet' -ServerAddresses ('1.1.1.1','8.8.8.8')
    Write-Host "Dégradation IP : terminée."
}

function Degrader-Imprimante {
    Write-Host "Dégradation Imprimante : suppression de l'imprimante Imprimante-Comptabilite."
    Remove-Printer -Name 'Imprimante-Comptabilite'
    Write-Host "Dégradation Imprimante : terminée."
}

function Degrader-LogicielInterdit {
    Write-Host "Dégradation logiciel interdit : installation de qBittorrent."
    winget install --id qBittorrent.qBittorrent -e --silent --accept-package-agreements --accept-source-agreements
    Write-Host "Dégradation logiciel interdit : terminée."
}

function Degrader-Environnement {
    Write-Host "Dégradation environnement : pavé numérique, explorateur et Chrome remis par défaut."
    Set-ItemProperty -Path 'HKCU:\Control Panel\Keyboard' -Name 'InitialKeyboardIndicators' -Value '0'
    $adv = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
    Set-ItemProperty -Path $adv -Name 'HideFileExt' -Value 1 -Type DWord
    Set-ItemProperty -Path $adv -Name 'Hidden' -Value 2 -Type DWord
    Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer' -Name 'ConfirmFileDelete' -Value 0 -Type DWord
    Remove-Item -Path 'HKLM:\SOFTWARE\Policies\Google\Chrome' -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Dégradation environnement : terminée."
}

function Degrader-PareFeu {
    Write-Host "Dégradation firewall : désactivation du profil Public du pare-feu."
    Set-NetFirewallProfile -Profile Public -Enabled False
    Write-Host "Dégradation firewall : terminée."
}

function Degrader-Compte {
    Write-Host "Dégradation compte : création du compte local non prévu 'stagiaire'."
    New-LocalUser -Name 'stagiaire' -NoPassword | Out-Null
    Write-Host "Dégradation compte : terminée."
}

function Degrader-Service {
    Write-Host "Dégradation service : arrêt et désactivation du service Audiosrv."
    Stop-Service -Name 'Audiosrv' -Force
    Set-Service -Name 'Audiosrv' -StartupType Disabled
    Write-Host "Dégradation service : terminée."
}

function Degrader-LogicielSocle {
    Write-Host "Dégradation logiciel : désinstallation de 7-Zip (logiciel du socle)."
    winget uninstall --id 7zip.7zip -e --silent --accept-source-agreements
    Write-Host "Dégradation logiciel : terminée (à vérifier avec la recette)."
}

Degrader-Imprimante
Degrader-LogicielInterdit
Degrader-LogicielSocle
Degrader-Environnement
Degrader-PareFeu
Degrader-Compte
Degrader-IP
Degrader-Service
Degrader-Nom