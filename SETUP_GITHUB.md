# 🚀 Setup GitHub - Istruzioni Rapide

## Opzione 1: GitHub CLI (Consigliata - 30 secondi)

```bash
# 1. Assicurati di essere autenticato
git remote remove origin 2>/dev/null; \
git remote add origin https://github.com/$(gh api user -q .login)/auto-broker.git; \
gh repo create auto-broker --public --description "AUTO-BROKER Logistics Platform" --source=. --push
```

## Opzione 2: Manuale (2 minuti)

### Step 1: Crea Repository
- Vai su: https://github.com/new
- **Repository name**: `auto-broker`
- **Description**: `AUTO-BROKER Logistics Platform - Big Tech Testing 2026`
- **Public** o **Private** (a tua scelta)
- ⚠️ **NON** spuntare "Initialize this repository with a README"
- Clicca **Create repository**

### Step 2: Connetti Locale → Remoto

Copia e incolla questi comandi nel terminale:

```bash
cd ~/Desktop/auto-broker
git remote remove origin 2>/dev/null
git remote add origin https://github.com/TUO_USERNAME/auto-broker.git
git push -u origin main
```

**Sostituisci `TUO_USERNAME` con il tuo username GitHub!**

## Step 3: Verifica

Dopo aver eseguito i comandi sopra:

```bash
./ship
```

Oppure manualmente:

```bash
open https://github.com/$(git remote get-url origin | sed 's/.*github.com\///' | sed 's/\.git//')/actions
```

---

## ✅ Checklist Post-Setup

- [ ] Repository creato su GitHub
- [ ] Codice pushato (git push)
- [ ] GitHub Actions workflow attivo
- [ ] Coverage 100% raggiunta

🎉 **Fatto! Ora hai una pipeline CI/CD enterprise-grade!**
