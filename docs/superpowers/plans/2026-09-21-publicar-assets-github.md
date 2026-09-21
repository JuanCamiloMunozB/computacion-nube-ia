# Publicar skills, modelos y documentación en GitHub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Confirmar y publicar en GitHub las skills, los archivos de modelos y la documentación del proyecto sin incluir secretos ni artefactos locales.

**Architecture:** Auditar el inventario versionado y las reglas de exclusión, validar que los archivos objetivo están presentes y luego sincronizar `main` con `origin/main`. Si la auditoría genera cambios, se agrupan en un commit documental y se publica mediante `git push`.

**Tech Stack:** Git, Markdown, skills locales, modelos scikit-learn/LightGBM/XGBoost en formato Joblib.

**Spec:** Solicitud del usuario: “subime las skills porfavor, archivos modelos y documentacion a github porfavor”.

## Global Constraints

- No subir credenciales, archivos `.env`, cachés, entornos virtuales ni el contenido excluido de `docReference/`.
- Mantener el remoto y la rama actuales: `origin` y `main`.
- Verificar el contenido antes de hacer `push`.

---

### Task 1: Auditar el contenido publicable

**Files:**
- Inspect: `.gitignore`
- Inspect: `.agents/skills/**`, `.claude/skills/**`
- Inspect: `modelo_churn_*/model.joblib`
- Inspect: `README.md`, `*.md`, `*.ipynb`, `*.pptx`

**Interfaces:**
- Consumes: estado local del repositorio y referencia `origin/main`.
- Produces: inventario de archivos versionados y resultado de la comprobación de secretos/artefactos.

- [ ] **Step 1: Listar estado, remoto e inventario de archivos**

```bash
git status --short --branch
git remote -v
git ls-files
```

- [ ] **Step 2: Comprobar que no hay archivos sensibles preparados**

```bash
git ls-files | rg '(^|/)(\.env|.*\.pem|.*\.key)$|__pycache__|\.venv'
```

Expected: sin coincidencias.

- [ ] **Step 3: Validar espacios y tamaño de los artefactos objetivo**

```bash
git diff --check
du -sh .agents/skills .claude/skills modelo_churn_* docs *.md *.ipynb *.pptx 2>/dev/null
```

Expected: sin errores de whitespace y archivos dentro del tamaño razonable para Git.

### Task 2: Sincronizar GitHub

**Files:**
- Modify: any audited files that are intentionally pending in the working tree

**Interfaces:**
- Consumes: inventario validado en Task 1.
- Produces: `origin/main` apuntando al commit local que contiene las skills, modelos y documentación.

- [ ] **Step 1: Confirmar la referencia remota de `main`**

```bash
git ls-remote origin refs/heads/main
```

- [ ] **Step 2: Crear un commit solo si existen cambios auditados**

```bash
git add .agents/skills .claude/skills modelo_churn_* docs README.md '*.md' '*.ipynb' '*.pptx'
git diff --cached --check
git commit -m "docs: publish skills models and documentation"
```

Expected: si no hay cambios, Git informa que el árbol está limpio y no se crea un commit vacío.

- [ ] **Step 3: Publicar `main` en GitHub**

```bash
git push origin main
```

- [ ] **Step 4: Verificar que local y remoto quedaron alineados**

```bash
git status --short --branch
git ls-remote origin refs/heads/main
git log -1 --oneline --decorate
```

Expected: árbol limpio y `origin/main` en el mismo commit que `HEAD`.
