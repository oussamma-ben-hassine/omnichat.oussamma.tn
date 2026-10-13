# Guide d'Utilisation : Pont Meta & Résumé Quotidien IA

Ce projet permet de connecter tes comptes personnels Facebook Messenger et Instagram à un serveur Matrix léger (Conduit) et de synthétiser quotidiennement tes échanges grâce à ton service IA.

---

## 1. Description des Composants

| Composant | Image / Rôle | Objectif |
| :--- | :--- | :--- |
| **Conduit** | `matrixconduit/matrix-conduit` | Serveur Matrix ultra-léger en Rust (< 50 Mo RAM). Il sert de hub local pour stocker tes messages en toute confidentialité. |
| **Mautrix-Meta** | `dock.mau.dev/mautrix/meta` | Pont (Bridge) qui se connecte à tes sessions Facebook / Instagram personnelles pour acheminer les messages vers Conduit. |
| **Matrix Summarizer** | Service FastAPI / Python | Agent IA qui interroge Conduit tous les soirs (ou à la demande), filtre les messages de la journée et génère un résumé structuré via ton API IA. |

---

## 2. Déploiement sur Coolify

### Option A : Déploiement Docker Compose dans Coolify
1. Dans Coolify (`https://coolify.oussamma.tn`), crée une nouvelle ressource de type **Docker Compose**.
2. Colle le contenu de `docker-compose.yml`.
3. Assigne les variables d'environnement suivantes :
   - `SUMMARIZER_BOT_PASSWORD`: Mot de passe du compte bot Matrix local.
   - `AI_API_KEY`: Ta clé d'API pour `ai.oussamma.tn`.
   - `AI_PROXY_URL`: `https://ai.oussamma.tn/v1`

---

## 3. Configuration Initiale du Pont Meta

1. Une fois les conteneurs démarrés, génère la configuration initiale du bridge :
   ```bash
   docker exec -it <nom_du_conteneur_mautrix_meta> /usr/bin/mautrix-meta -g
   ```
2. Associe le bridge à Conduit en enregistrant le fichier de registration `appservice-registration.yaml` dans Conduit.
3. Ouvre une discussion avec le bot du bridge (`@metabot:matrix.oussamma.tn`) :
   - Tape : `login-facebook` pour lier Messenger via tes identifiants ou cookies de session.
   - Tape : `login-instagram` pour lier tes DM Instagram.
4. Une fois connecté, le bridge synchronise automatiquement tes contacts et tes messages privés.

---

## 4. Consultation du Résumé IA

- **Automatique** : Une tâche planifiée (Cron) interroge le bridge chaque soir à 23h00.
- **À la demande (API)** :
  ```http
  GET http://matrix-summarizer:8000/api/digest/now
  ```
  Retourne un JSON avec le nombre de messages reçus et le compte-rendu généré par le modèle LLM.
