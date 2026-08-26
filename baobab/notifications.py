"""
Notifications email via Resend.
Utilisé pour les alertes paiement admin et confirmations utilisateur.
"""

import html as _html_lib
import logging
import os

import httpx
from baobab.billing import format_price

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "BAOBAB <contact@vaeg-conformite.fr>")
ADMIN_EMAIL = os.getenv("BAOBAB_ADMIN_EMAIL", "")
APP_URL = os.getenv("APP_URL", "https://www.vaegbaobab.com")


def esc(value) -> str:
    """
    Échappe une valeur avant interpolation dans un template HTML d'email.

    Les emails transactionnels sont construits par f-string à partir de
    champs saisis par l'utilisateur (owner_name, organization_name,
    phone_number...). Sans échappement, un nom d'organisation contenant
    du HTML/JS casse la mise en page ou insère des liens trompeurs dans
    un email envoyé au client ET à l'équipe BAOBAB — cf. audit sécurité
    (variante du chapitre XSS du livre appliquée au rendu email).
    """
    return _html_lib.escape(str(value if value is not None else ""), quote=True)


async def _send(to: str, subject: str, html: str, *, bcc: list[str] | None = None) -> bool:
    if not to:
        logger.warning("Destinataire manquant — email ignoré : %s", subject)
        return False
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY non configurée — email ignoré : %s", subject)
        return False
    try:
        payload: dict = {
            "from": RESEND_FROM,
            "to": [to],
            "subject": subject,
            "html": html,
        }
        # Le BCC n'est ajouté qu'explicitement, jamais par défaut : un
        # email contenant un mot de passe temporaire ou un token d'accès
        # ne doit pas être dupliqué systématiquement vers une boîte tierce
        # (cf. audit sécurité — duplication inutile d'un secret).
        if bcc:
            payload["bcc"] = bcc
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json=payload,
            )
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.error("Échec envoi email (%s) : %s", subject, exc)
        return False


async def notify_legal_watch_alert(to: str, watch_name: str, event: dict) -> bool:
    """Alerte documentaire envoyée après validation automatique et consentement."""
    title = esc(event.get("title", "Publication juridique"))
    source = esc(event.get("source_code", "Source officielle"))
    watch = esc(watch_name)
    url = esc(event.get("artifact_url", ""))
    score = esc(event.get("validation_score", ""))
    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#1B3A2D;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">BAOBAB — Veille juridique</h1>
      </div>
      <div style="padding:24px;border:1px solid #ddd;border-radius:0 0 8px 8px">
        <p style="font-size:12px;color:#666">Surveillance : <strong>{watch}</strong></p>
        <h2 style="font-size:18px">{title}</h2>
        <p style="font-size:13px;color:#555">Source : {source} · Score documentaire : {score}/100</p>
        <p style="font-size:12px;color:#777">La provenance et la stabilité du document ont été
        validées automatiquement. Son impact juridique reste à qualifier.</p>
        <a href="{url}" style="display:inline-block;background:#BF4E1E;color:#fff;padding:11px 18px;
           border-radius:6px;text-decoration:none;font-weight:bold">Consulter la source officielle</a>
      </div>
    </div>"""
    return await _send(to, f"[BAOBAB] {event.get('title', 'Nouvelle publication juridique')}", body)


async def notify_user_workspace_created(workspace: dict, clear_password: str | None = None) -> bool:
    """Email de bienvenue self-service : identifiants de connexion + lien vers les formules."""
    owner_name = esc(workspace["owner_name"])
    organization_name = esc(workspace["organization_name"])
    email = esc(workspace["email"])
    territory = esc(workspace["territory"])
    workspace_id = esc(workspace["workspace_id"])

    pwd_block = ""
    if clear_password:
        pwd_block = f"""
        <div style="background:#fff7f0;border:1.5px solid #BF4E1E;border-radius:8px;padding:16px;margin:16px 0">
          <p style="margin:0 0 10px;font-size:11px;color:#7A5035;text-transform:uppercase;letter-spacing:1px;font-weight:700">
            Mot de passe temporaire — à changer à la première connexion
          </p>
          <p style="margin:0;font-family:monospace;font-size:16px;color:#BF4E1E;font-weight:700;letter-spacing:1px">
            {esc(clear_password)}
          </p>
        </div>"""
    else:
        pwd_block = """
        <p style="font-size:13px;color:#555;margin:12px 0">
          Utilisez le mot de passe que vous avez défini lors de votre inscription.
        </p>"""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#BF4E1E;padding:28px 24px;border-radius:8px 8px 0 0">
        <h1 style="color:#FDF8F3;margin:0;font-size:22px;font-weight:700">BAOBAB — Votre espace est prêt</h1>
        <p style="color:rgba(253,248,243,.75);margin:6px 0 0;font-size:13px">Legal Operating System for Africa</p>
      </div>
      <div style="background:#f9f9f9;padding:28px 24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p style="margin:0 0 8px">Bonjour <strong>{owner_name}</strong>,</p>
        <p style="margin:0 0 20px;color:#444;font-size:14px">
          Votre espace BAOBAB pour <strong>{organization_name}</strong> a bien été créé.
          Voici vos identifiants de connexion.
        </p>
        <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:16px">
          <table style="width:100%;border-collapse:collapse">
            <tr>
              <td style="padding:6px 0;color:#888;font-size:12px;width:120px">Email</td>
              <td style="padding:6px 0;font-weight:700;font-size:14px">{email}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#888;font-size:12px">Organisation</td>
              <td style="padding:6px 0;font-size:14px">{organization_name}</td>
            </tr>
            <tr>
              <td style="padding:6px 0;color:#888;font-size:12px">Territoire</td>
              <td style="padding:6px 0;font-size:14px">{territory}</td>
            </tr>
          </table>
        </div>
        {pwd_block}
        <p style="font-size:13px;color:#555;margin:16px 0">
          Choisissez votre formule d'abonnement pour accéder à l'ensemble des services BAOBAB.
        </p>
        <a href="{APP_URL}" style="display:inline-block;background:#BF4E1E;color:#FDF8F3;padding:13px 28px;
           border-radius:6px;text-decoration:none;font-weight:700;font-size:14px">
          Accéder à BAOBAB →
        </a>
        <p style="margin:24px 0 0;font-size:11px;color:#bbb;border-top:1px solid #eee;padding-top:16px">
          Cet email est confidentiel. Ne le transmettez pas à des tiers. ·
          ID espace : {workspace_id}
        </p>
      </div>
    </div>
    """
    # Pas de BCC ici : cet email contient un mot de passe temporaire en
    # clair, il ne doit être délivré qu'à son destinataire légitime.
    return await _send(
        workspace["email"],
        f"[BAOBAB] Votre espace {workspace['organization_name']} est créé",
        html,
    )


async def notify_superadmin_workspace_created(workspace: dict, clear_password: str | None) -> bool:
    """Email envoyé au client quand le superadmin crée son compte — inclut le mdp temporaire."""
    owner_name = esc(workspace["owner_name"])
    organization_name = esc(workspace["organization_name"])
    email = esc(workspace["email"])
    plan = esc(str(workspace.get("plan", "")).upper())
    workspace_id = esc(workspace["workspace_id"])

    pwd_section = f"""
        <div style="background:#fff7f0;border:1.5px solid #BF4E1E;border-radius:8px;padding:18px;margin:20px 0">
          <p style="margin:0 0 6px;font-size:11px;color:#7A5035;text-transform:uppercase;letter-spacing:1px;font-weight:700">
            Mot de passe temporaire
          </p>
          <p style="margin:0 0 10px;font-family:monospace;font-size:18px;color:#BF4E1E;font-weight:700;letter-spacing:2px">
            {esc(clear_password) if clear_password else '(mot de passe personnalisé)'}
          </p>
          <p style="margin:0;font-size:12px;color:#888">
            Changez ce mot de passe dès votre première connexion depuis les paramètres de votre espace.
          </p>
        </div>""" if clear_password else ""

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#1B3A2D;padding:28px 24px;border-radius:8px 8px 0 0">
        <h1 style="color:#FDF8F3;margin:0;font-size:22px;font-weight:700">BAOBAB — Votre accès est activé</h1>
        <p style="color:rgba(253,248,243,.65);margin:6px 0 0;font-size:13px">Legal Operating System for Africa</p>
      </div>
      <div style="background:#f9f9f9;padding:28px 24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p style="margin:0 0 8px">Bonjour <strong>{owner_name}</strong>,</p>
        <p style="margin:0 0 20px;color:#444;font-size:14px">
          L'équipe BAOBAB a créé votre espace pour <strong>{organization_name}</strong>.
          Voici vos identifiants pour accéder à la plateforme.
        </p>
        <div style="background:#fff;border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:4px">
          <table style="width:100%;border-collapse:collapse">
            <tr>
              <td style="padding:7px 0;color:#888;font-size:12px;width:130px">Email de connexion</td>
              <td style="padding:7px 0;font-weight:700;font-size:14px">{email}</td>
            </tr>
            <tr style="border-top:1px solid #f0f0f0">
              <td style="padding:7px 0;color:#888;font-size:12px">Organisation</td>
              <td style="padding:7px 0;font-size:14px">{organization_name}</td>
            </tr>
            <tr style="border-top:1px solid #f0f0f0">
              <td style="padding:7px 0;color:#888;font-size:12px">Formule</td>
              <td style="padding:7px 0;font-size:14px;font-weight:600;color:#1B3A2D">{plan}</td>
            </tr>
          </table>
        </div>
        {pwd_section}
        <a href="{APP_URL}" style="display:inline-block;background:#1B3A2D;color:#FDF8F3;padding:13px 28px;
           border-radius:6px;text-decoration:none;font-weight:700;font-size:14px;margin-top:8px">
          Accéder à mon espace BAOBAB →
        </a>
        <p style="margin:24px 0 0;font-size:11px;color:#bbb;border-top:1px solid #eee;padding-top:16px">
          Cet email est confidentiel. Pour toute question : <a href="mailto:contact@vaeg-conformite.fr" style="color:#BF4E1E">contact@vaeg-conformite.fr</a> ·
          ID espace : {workspace_id}
        </p>
      </div>
    </div>
    """
    # Pas de BCC ici non plus : mot de passe temporaire en clair.
    return await _send(
        workspace["email"],
        f"[BAOBAB] Votre espace {workspace['organization_name']} est activé",
        html,
    )


async def notify_admin_new_workspace(workspace: dict) -> bool:
    """Alerte le compte contact dès qu'un nouveau client crée son espace."""
    owner_name = esc(workspace["owner_name"])
    organization_name = esc(workspace["organization_name"])
    email = esc(workspace["email"])
    territory = esc(workspace["territory"])
    workspace_id = esc(workspace["workspace_id"])

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#A67C2A;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:#FDF8F3;margin:0;font-size:20px">🌳 BAOBAB — Nouveau client inscrit</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p style="margin:0 0 16px">Un nouveau client vient de créer son espace BAOBAB.</p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
          <tr><td style="padding:8px;color:#555;width:40%">Organisation</td>
              <td style="padding:8px;font-weight:bold">{organization_name}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Contact</td>
              <td style="padding:8px">{owner_name} — {email}</td></tr>
          <tr><td style="padding:8px;color:#555">Territoire</td>
              <td style="padding:8px">{territory}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Statut</td>
              <td style="padding:8px">Espace gratuit créé — formule non encore choisie</td></tr>
          <tr><td style="padding:8px;color:#555">ID espace</td>
              <td style="padding:8px;font-family:monospace;font-size:12px">{workspace_id}</td></tr>
        </table>
        <p style="font-size:12px;color:#888;margin:0">
          Un second email suivra si ce client soumet une demande d'abonnement.
        </p>
      </div>
    </div>
    """
    if not ADMIN_EMAIL:
        logger.warning("BAOBAB_ADMIN_EMAIL non configurée — alerte nouveau client ignorée.")
        return False
    return await _send(
        ADMIN_EMAIL,
        f"[BAOBAB] Nouveau client — {workspace['organization_name']} ({workspace['territory']})",
        html,
    )


async def notify_admin_payment_pending(payment: dict, workspace: dict) -> bool:
    """Alerte l'admin qu'un paiement est en attente d'approbation."""
    plan_labels = {"basic": "Professionnel", "premium": "Cabinet & Équipe"}
    provider_labels = {"orange_money": "Orange Money", "mtn_money": "MTN Mobile Money", "wave": "Wave", "stripe": "Carte bancaire Stripe"}

    organization_name = esc(workspace["organization_name"])
    owner_name = esc(workspace["owner_name"])
    email = esc(workspace["email"])
    plan_label = esc(plan_labels.get(payment["plan"], payment["plan"]))
    provider_label = esc(provider_labels.get(payment["provider"], payment["provider"]))
    phone_number = esc(payment["phone_number"])
    provider_reference = esc(payment["provider_reference"])
    payment_id = esc(payment["payment_id"])
    payment_amount = payment.get("amount", payment.get("amount_xof", 0)) or 0
    payment_currency = payment.get("currency", "XOF")
    formatted_amount = esc(format_price(payment_amount, payment_currency))
    confirm_url = esc(f"{APP_URL}/api/v1/accounts/payments/{payment['payment_id']}/confirm")

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#1B4332;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">🌳 BAOBAB — Paiement en attente</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p style="margin:0 0 16px">Un nouveau paiement attend votre validation.</p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
          <tr><td style="padding:8px;color:#555;width:40%">Workspace</td>
              <td style="padding:8px;font-weight:bold">{organization_name}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Contact</td>
              <td style="padding:8px">{owner_name} — {email}</td></tr>
          <tr><td style="padding:8px;color:#555">Formule</td>
              <td style="padding:8px;font-weight:bold">{plan_label}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Moyen de paiement</td>
              <td style="padding:8px">{provider_label}</td></tr>
          <tr><td style="padding:8px;color:#555">Numéro mobile</td>
              <td style="padding:8px">{phone_number}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Montant</td>
              <td style="padding:8px;font-weight:bold">{formatted_amount}</td></tr>
          <tr><td style="padding:8px;color:#555">Référence BAOBAB</td>
              <td style="padding:8px;font-family:monospace">{provider_reference}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">ID Paiement</td>
              <td style="padding:8px;font-family:monospace">{payment_id}</td></tr>
        </table>
        <p style="margin:0 0 8px;color:#555;font-size:13px">
          Pour confirmer ce paiement, appelez l'endpoint suivant avec votre token superadmin :
        </p>
        <div style="background:#1B4332;color:#a8e6c0;padding:12px;border-radius:6px;font-family:monospace;font-size:12px;word-break:break-all">
          POST {confirm_url}<br>
          Header: Authorization: Bearer &lt;votre-token-superadmin&gt;
        </div>
        <p style="margin:16px 0 0;font-size:12px;color:#888">
          Cet email a été généré automatiquement par BAOBAB. Ne pas répondre.
        </p>
      </div>
    </div>
    """
    if not ADMIN_EMAIL:
        logger.warning("BAOBAB_ADMIN_EMAIL non configurée — alerte paiement en attente ignorée.")
        return False
    return await _send(ADMIN_EMAIL, f"[BAOBAB] Paiement en attente — {workspace['organization_name']}", html)


async def notify_user_payment_confirmed(payment: dict, workspace: dict) -> bool:
    """Notifie l'utilisateur que son paiement a été validé et lui donne son accès."""
    plan_labels = {"basic": "Professionnel", "premium": "Cabinet & Équipe"}

    owner_name = esc(workspace["owner_name"])
    organization_name = esc(workspace["organization_name"])
    plan_label = esc(plan_labels.get(payment["plan"], payment["plan"]))
    user_token = esc(workspace["user_token"])
    provider_reference = esc(payment["provider_reference"])

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#1B4332;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">🌳 BAOBAB — Votre accès est activé !</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p>Bonjour <strong>{owner_name}</strong>,</p>
        <p>Votre abonnement <strong>{plan_label}</strong> a été validé.
           Votre espace BAOBAB est maintenant pleinement actif.</p>
        <div style="background:#fff;border:2px solid #1B4332;border-radius:8px;padding:16px;margin:20px 0">
          <p style="margin:0 0 8px;font-size:13px;color:#555">Votre code d'accès :</p>
          <p style="margin:0;font-family:monospace;font-size:16px;color:#1B4332;font-weight:bold;word-break:break-all">
            {user_token}
          </p>
        </div>
        <p style="font-size:13px;color:#555">
          Conservez ce code précieusement — il vous permet de vous connecter à votre espace.
        </p>
        <a href="{APP_URL}" style="display:inline-block;background:#1B4332;color:#fff;padding:12px 24px;
           border-radius:6px;text-decoration:none;font-weight:bold;margin-top:8px">
          Accéder à BAOBAB →
        </a>
        <p style="margin:20px 0 0;font-size:12px;color:#888">
          Référence : {provider_reference} · Organisation : {organization_name}
        </p>
      </div>
    </div>
    """
    # Pas de BCC : cet email contient le token d'accès permanent du client.
    return await _send(
        workspace["email"],
        "[BAOBAB] Votre abonnement est activé — accédez à votre espace",
        html,
    )
