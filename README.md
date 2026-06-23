# projet-datawarehouse
projet d'entrepôt de données pour l'analyse des maladies chroniques fréquentes  


Pour cloner le projet sur votre pc bien vouloir suivre ces suites de commandes: 

1. Installer Git LFS (une seule fois par machine)

Windows (Invite de commandes ou PowerShell) :

cmdwinget install GitHub.GitLFS

macOS :

bashbrew install git-lfs

Linux (Debian/Ubuntu) :

bashsudo apt install git-lfs

2. Activer Git LFS (une seule fois par machine)
bashgit lfs install

3. Cloner le dépôt
bashgit clone https://github.com/Samuela2375/projet-datawarehouse.git
cd projet-datawarehouse

4. Vérifier que le fichier CSV est bien récupéré en entier
bashgit lfs ls-files
Ils doivent voir U.S._Chronic_Disease_Indicators.csv apparaître dans la liste.

5. Si le fichier semble anormalement petit (quelques Ko au lieu de ~117 Mo)
bashgit lfs pull

Pour ceux qui ont déjà cloné le dépôt avant ta correction (donc avant que le CSV soit en LFS), ils devront plutôt faire :
bashgit lfs install
git pull
git lfs pull