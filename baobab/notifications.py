"""
Notifications email via Resend.
Utilisé pour les alertes paiement admin et confirmations utilisateur.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "BAOBAB <contact@vaeg-conformite.fr>")
ADMIN_EMAIL = "yboulock@gmail.com"
APP_URL = os.getenv("APP_URL", "https://www.vaegbaobab.com")


async def _send(to: str, subject: str, html: str) -> bool:
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY non configurée — email ignoré : %s", subject)
        return False
    try:
        payload: dict = {
            "from": RESEND_FROM,
            "to": [to],
            "bcc": [ADMIN_EMAIL],
            "subject": subject,
            "html": html,
        }
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


async def notify_user_workspace_created(workspace: dict) -> bool:
    """Email de bienvenue envoyé dès la création du compte, avec le code d'accès conservé."""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#BF4E1E;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:#FDF8F3;margin:0;font-size:20px">🌳 BAOBAB — Votre espace est créé</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p>Bonjour <strong>{workspace['owner_name']}</strong>,</p>
        <p style="margin:8px 0 16px">
          Votre espace BAOBAB pour <strong>{workspace['organization_name']}</strong> a bien été créé.
          Conservez précieusement le code ci-dessous — il vous permettra de vous reconnecter à tout moment.
        </p>
        <div style="background:#fff;border:2px solid #BF4E1E;border-radius:8px;padding:16px;margin:20px 0">
          <p style="margin:0 0 6px;font-size:12px;color:#7A5035;text-transform:uppercase;letter-spacing:1px">
            Votre code d'accès personnel
          </p>
          <p style="margin:0;font-family:monospace;font-size:15px;color:#BF4E1E;font-weight:bold;word-break:break-all">
            {workspace['user_token']}
          </p>
        </div>
        <p style="font-size:13px;color:#555;margin-bottom:16px">
          Pour activer votre accès complet, choisissez une formule d'abonnement sur notre site.<br>
          Votre demande sera traitée sous <strong>24h</strong>.
        </p>
        <a href="{APP_URL}" style="display:inline-block;background:#BF4E1E;color:#FDF8F3;padding:12px 24px;
           border-radius:6px;text-decoration:none;font-weight:bold">
          Choisir ma formule →
        </a>
        <p style="margin:20px 0 0;font-size:11px;color:#aaa">
          Organisation : {workspace['organization_name']} · Territoire : {workspace['territory']} ·
          ID espace : {workspace['workspace_id']}
        </p>
      </div>
    </div>
    """
    return await _send(
        workspace["email"],
        "[BAOBAB] Votre espace est créé — conservez votre code d'accès",
        html,
    )


async def notify_admin_payment_pending(payment: dict, workspace: dict) -> bool:
    """Alerte l'admin qu'un paiement est en attente d'approbation."""
    plan_labels = {"basic": "Basic — 5 000 XOF/mois", "premium": "Premium — 10 000 XOF/mois"}
    provider_labels = {"orange_money": "Orange Money", "mtn_money": "MTN Mobile Money", "wave": "Wave"}

    confirm_url = f"{APP_URL}/api/v1/accounts/payments/{payment['payment_id']}/confirm"

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#1B4332;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">🌳 BAOBAB — Paiement en attente</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p style="margin:0 0 16px">Un nouveau paiement attend votre validation.</p>
        <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
          <tr><td style="padding:8px;color:#555;width:40%">Workspace</td>
              <td style="padding:8px;font-weight:bold">{workspace['organization_name']}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Contact</td>
              <td style="padding:8px">{workspace['owner_name']} — {workspace['email']}</td></tr>
          <tr><td style="padding:8px;color:#555">Formule</td>
              <td style="padding:8px;font-weight:bold">{plan_labels.get(payment['plan'], payment['plan'])}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Moyen de paiement</td>
              <td style="padding:8px">{provider_labels.get(payment['provider'], payment['provider'])}</td></tr>
          <tr><td style="padding:8px;color:#555">Numéro mobile</td>
              <td style="padding:8px">{payment['phone_number']}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">Montant</td>
              <td style="padding:8px;font-weight:bold">{payment['amount_xof']:,} XOF</td></tr>
          <tr><td style="padding:8px;color:#555">Référence BAOBAB</td>
              <td style="padding:8px;font-family:monospace">{payment['provider_reference']}</td></tr>
          <tr style="background:#fff"><td style="padding:8px;color:#555">ID Paiement</td>
              <td style="padding:8px;font-family:monospace">{payment['payment_id']}</td></tr>
        </table>
        <p style="margin:0 0 8px;color:#555;font-size:13px">
          Pour confirmer ce paiement, appelez l'endpoint suivant avec votre token superadmin :
        </p>
        <div style="background:#1B4332;color:#a8e6c0;padding:12px;border-radius:6px;font-family:monospace;font-size:12px;word-break:break-all">
          POST {confirm_url}<br>
          Header: X-Superadmin-Token: &lt;votre-token&gt;
        </div>
        <p style="margin:16px 0 0;font-size:12px;color:#888">
          Cet email a été généré automatiquement par BAOBAB. Ne pas répondre.
        </p>
      </div>
    </div>
    """
    return await _send(ADMIN_EMAIL, f"[BAOBAB] Paiement en attente — {workspace['organization_name']}", html)


async def notify_user_payment_confirmed(payment: dict, workspace: dict) -> bool:
    """Notifie l'utilisateur que son paiement a été validé et lui donne son accès."""
    plan_labels = {"basic": "Basic", "premium": "Premium"}
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;color:#1a1a1a">
      <div style="background:#1B4332;padding:24px;border-radius:8px 8px 0 0">
        <h1 style="color:#fff;margin:0;font-size:20px">🌳 BAOBAB — Votre accès est activé !</h1>
      </div>
      <div style="background:#f9f9f9;padding:24px;border-radius:0 0 8px 8px;border:1px solid #e0e0e0">
        <p>Bonjour <strong>{workspace['owner_name']}</strong>,</p>
        <p>Votre abonnement <strong>{plan_labels.get(payment['plan'], payment['plan'])}</strong> a été validé.
           Votre espace BAOBAB est maintenant pleinement actif.</p>
        <div style="background:#fff;border:2px solid #1B4332;border-radius:8px;padding:16px;margin:20px 0">
          <p style="margin:0 0 8px;font-size:13px;color:#555">Votre code d'accès :</p>
          <p style="margin:0;font-family:monospace;font-size:16px;color:#1B4332;font-weight:bold;word-break:break-all">
            {workspace['user_token']}
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
          Référence : {payment['provider_reference']} · Organisation : {workspace['organization_name']}
        </p>
      </div>
    </div>
    """
    return await _send(
        workspace["email"],
        "[BAOBAB] Votre abonnement est activé — accédez à votre espace",
        html,
    )
