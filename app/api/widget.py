"""Widget serving routes."""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import get_db
from app.models.business import Business

logger = logging.getLogger(__name__)

router = APIRouter()

# Set up Jinja2 environment for widget templates
_widget_template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "widget")
_jinja_env = Environment(
    loader=FileSystemLoader(_widget_template_dir),
    autoescape=False,
)


@router.get("/widget/{slug}.js")
async def serve_widget(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve the chat widget loader script with business-specific config."""
    result = await db.execute(
        select(Business).where(
            Business.slug == slug,
            Business.is_active == True,  # noqa: E712
        )
    )
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    settings = get_settings()

    # Extract branding config
    branding = business.branding or {}
    primary_color = branding.get("primary_color", "#2563eb")
    logo_url = branding.get("logo_url", "")
    welcome_message = branding.get("welcome_message", "Hi! How can we help you today?")

    # Determine WebSocket URL
    base_url = settings.BASE_URL
    ws_scheme = "wss" if base_url.startswith("https") else "ws"
    ws_host = base_url.replace("https://", "").replace("http://", "")
    ws_url = f"{ws_scheme}://{ws_host}/ws/chat/{slug}"

    template_context = {
        "business_name": business.name,
        "slug": slug,
        "business_slug": slug,
        "ws_url": ws_url,
        "primary_color": primary_color,
        "logo_url": logo_url,
        "welcome_message": welcome_message,
        "base_url": base_url,
    }

    try:
        template = _jinja_env.get_template("widget-loader.js.jinja2")
        js_content = template.render(**template_context)
    except Exception:
        logger.exception("Failed to render widget template for slug=%s", slug)
        # Return a minimal fallback widget script
        js_content = _fallback_widget_script(template_context)

    return Response(
        content=js_content,
        media_type="application/javascript",
        headers={
            "Cache-Control": "public, max-age=300",
            "Access-Control-Allow-Origin": "*",
        },
    )


def _fallback_widget_script(ctx: dict) -> str:
    """Generate a minimal widget script if the template is missing."""
    return f"""
(function() {{
  'use strict';
  var config = {{
    businessName: {_js_str(ctx['business_name'])},
    businessSlug: {_js_str(ctx['business_slug'])},
    wsUrl: {_js_str(ctx['ws_url'])},
    primaryColor: {_js_str(ctx['primary_color'])},
    logoUrl: {_js_str(ctx['logo_url'])},
    welcomeMessage: {_js_str(ctx['welcome_message'])},
    baseUrl: {_js_str(ctx['base_url'])}
  }};

  var style = document.createElement('style');
  style.textContent = '\\
    #ib-chat-widget {{ position:fixed; bottom:20px; right:20px; z-index:99999; font-family:system-ui,sans-serif; }}\\
    #ib-chat-toggle {{ width:60px; height:60px; border-radius:50%; background:' + config.primaryColor + '; color:#fff; border:none; cursor:pointer; font-size:24px; box-shadow:0 4px 12px rgba(0,0,0,0.15); display:flex; align-items:center; justify-content:center; }}\\
    #ib-chat-window {{ display:none; width:380px; height:520px; background:#fff; border-radius:12px; box-shadow:0 8px 30px rgba(0,0,0,0.12); flex-direction:column; overflow:hidden; margin-bottom:12px; }}\\
    #ib-chat-window.open {{ display:flex; }}\\
    #ib-chat-header {{ background:' + config.primaryColor + '; color:#fff; padding:16px; font-weight:600; display:flex; justify-content:space-between; align-items:center; }}\\
    #ib-chat-messages {{ flex:1; overflow-y:auto; padding:16px; }}\\
    .ib-msg {{ margin-bottom:12px; max-width:80%; padding:10px 14px; border-radius:12px; font-size:14px; line-height:1.4; }}\\
    .ib-msg.assistant {{ background:#f0f0f0; border-bottom-left-radius:4px; }}\\
    .ib-msg.user {{ background:' + config.primaryColor + '; color:#fff; margin-left:auto; border-bottom-right-radius:4px; }}\\
    #ib-chat-input-area {{ display:flex; border-top:1px solid #e0e0e0; padding:8px; }}\\
    #ib-chat-input {{ flex:1; border:1px solid #ddd; border-radius:8px; padding:10px 12px; font-size:14px; outline:none; }}\\
    #ib-chat-send {{ background:' + config.primaryColor + '; color:#fff; border:none; border-radius:8px; padding:10px 16px; margin-left:8px; cursor:pointer; font-size:14px; }}\\
  ';
  document.head.appendChild(style);

  var widget = document.createElement('div');
  widget.id = 'ib-chat-widget';
  widget.innerHTML = '\\
    <div id="ib-chat-window">\\
      <div id="ib-chat-header"><span>' + config.businessName + '</span><button onclick="document.getElementById(\\'ib-chat-window\\').classList.remove(\\'open\\')" style="background:none;border:none;color:#fff;font-size:18px;cursor:pointer;">&times;</button></div>\\
      <div id="ib-chat-messages"></div>\\
      <div id="ib-chat-input-area">\\
        <input id="ib-chat-input" type="text" placeholder="Type a message..." />\\
        <button id="ib-chat-send">Send</button>\\
      </div>\\
    </div>\\
    <button id="ib-chat-toggle">&#128172;</button>\\
  ';
  document.body.appendChild(widget);

  var ws = null;
  var messagesEl = null;

  function addMessage(text, role) {{
    if (!messagesEl) messagesEl = document.getElementById('ib-chat-messages');
    var div = document.createElement('div');
    div.className = 'ib-msg ' + role;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }}

  function connect() {{
    ws = new WebSocket(config.wsUrl);
    ws.onmessage = function(e) {{
      try {{
        var data = JSON.parse(e.data);
        if (data.content) addMessage(data.content, 'assistant');
      }} catch(err) {{}}
    }};
    ws.onclose = function() {{ ws = null; }};
  }}

  document.getElementById('ib-chat-toggle').addEventListener('click', function() {{
    var win = document.getElementById('ib-chat-window');
    win.classList.toggle('open');
    if (!ws) connect();
  }});

  function sendMsg() {{
    var input = document.getElementById('ib-chat-input');
    var text = input.value.trim();
    if (!text || !ws || ws.readyState !== 1) return;
    ws.send(JSON.stringify({{content: text}}));
    addMessage(text, 'user');
    input.value = '';
  }}

  document.getElementById('ib-chat-send').addEventListener('click', sendMsg);
  document.getElementById('ib-chat-input').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') sendMsg();
  }});
}})();
"""


def _js_str(value: str) -> str:
    """Safely encode a string for JavaScript."""
    import json
    return json.dumps(str(value))
