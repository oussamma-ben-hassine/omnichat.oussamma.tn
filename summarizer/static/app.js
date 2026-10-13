let currentTargetPlatform = 'facebook';
let activeRoomId = null;

// Initialisation
document.addEventListener('DOMContentLoaded', () => {
  loadConversations();
  checkPlatformStatus();
});

// Vérifier l'état de connexion des comptes
async function checkPlatformStatus() {
  try {
    const res = await fetch('/api/status');
    if (res.ok) {
      const data = await res.json();
      updatePill('fb', data.facebook);
      updatePill('ig', data.instagram);
    }
  } catch (e) {
    console.warn("Bridge non encore initialisé, mode démo/chargement.");
  }
}

function updatePill(platform, isConnected) {
  const textEl = document.getElementById(`${platform}-status-text`);
  const btn = document.querySelector(`#${platform}-status-pill .btn-connect`);
  if (isConnected) {
    textEl.textContent = 'Connecté ✅';
    textEl.style.color = '#4ade80';
    btn.textContent = 'Gérer';
  } else {
    textEl.textContent = 'Non connecté';
    textEl.style.color = '#94a3b8';
    btn.textContent = 'Lier';
  }
}

// Charger la liste des conversations captées
async function loadConversations() {
  const container = document.getElementById('conv-list');
  try {
    const res = await fetch('/api/conversations');
    if (res.ok) {
      const convs = await res.json();
      renderConversations(convs);
    } else {
      renderDemoConversations();
    }
  } catch (e) {
    renderDemoConversations();
  }
}

function renderDemoConversations() {
  const container = document.getElementById('conv-list');
  const demoList = [
    { id: 'room_fb_1', name: 'Karim (Messenger)', platform: 'fb', lastMessage: 'On se voit demain à 14h ?', time: 'Il y a 10 min' },
    { id: 'room_ig_2', name: 'Design Studio (Instagram)', platform: 'ig', lastMessage: 'Superbe réalisation !', time: 'Il y a 1h' },
    { id: 'room_fb_3', name: 'Famille (Groupe Messenger)', platform: 'fb', lastMessage: 'Oussama, tu viens pour le dîner ?', time: 'Il y a 3h' }
  ];
  renderConversations(demoList);
}

function renderConversations(list) {
  const container = document.getElementById('conv-list');
  container.innerHTML = '';
  if (list.length === 0) {
    container.innerHTML = '<div style="color:#94a3b8;font-size:12px;text-align:center;padding:12px;">Aucun message capté pour le moment.</div>';
    return;
  }

  list.forEach(c => {
    const item = document.createElement('div');
    item.className = `conv-item ${activeRoomId === c.id ? 'active' : ''}`;
    item.onclick = () => selectConversation(c);
    item.innerHTML = `
      <div class="conv-item-title">
        <span>${c.name}</span>
        <small style="color:#94a3b8;font-size:11px;">${c.time || ''}</small>
      </div>
      <div class="conv-item-preview">${c.lastMessage || 'Discussion ouverte'}</div>
    `;
    container.appendChild(item);
  });
}

// Sélectionner une discussion pour afficher son historique
async function selectConversation(conv) {
  activeRoomId = conv.id;
  document.getElementById('current-chat-title').textContent = conv.name;
  document.getElementById('current-chat-meta').textContent = `Canal : ${conv.platform === 'fb' ? 'Facebook Messenger' : 'Instagram DM'}`;

  // Mettre à jour la classe active
  document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));

  const container = document.getElementById('messages-container');
  container.innerHTML = '<div style="text-align:center;color:#94a3b8;margin:auto;">Chargement des messages...</div>';

  try {
    const res = await fetch(`/api/conversations/${conv.id}/messages`);
    if (res.ok) {
      const messages = await res.json();
      renderMessages(messages);
    } else {
      renderDemoMessages(conv.name);
    }
  } catch (e) {
    renderDemoMessages(conv.name);
  }
}

function renderDemoMessages(contactName) {
  const messages = [
    { sender: contactName, text: "Salut Oussama ! J'espère que tu vas bien.", time: "11:24", incoming: true },
    { sender: "Moi", text: "Salut ! Oui très bien, je travaille sur mes nouveaux projets.", time: "11:28", incoming: false },
    { sender: contactName, text: "Top ! Est-ce qu'on peut finaliser la revue du document ce soir ?", time: "11:30", incoming: true }
  ];
  renderMessages(messages);
}

function renderMessages(messages) {
  const container = document.getElementById('messages-container');
  container.innerHTML = '';
  messages.forEach(m => {
    const bubble = document.createElement('div');
    bubble.className = `message-bubble ${m.incoming ? 'incoming' : 'outgoing'}`;
    bubble.innerHTML = `
      <div class="message-sender">${m.sender}</div>
      <div class="message-text">${m.text}</div>
      <div class="message-time">${m.time}</div>
    `;
    container.appendChild(bubble);
  });
  container.scrollTop = container.scrollHeight;
}

// Générer le résumé quotidien IA
async function generateDailyDigest() {
  const panel = document.getElementById('digest-panel');
  const content = document.getElementById('digest-content');
  panel.style.display = 'flex';
  content.innerHTML = '🤖 <em>Interrogation de ai.oussamma.tn et synthèse de vos échanges en cours...</em>';

  try {
    const res = await fetch('/api/digest/now');
    const data = await res.json();
    content.textContent = data.summary;
  } catch (e) {
    content.innerHTML = `
📌 <strong>Résumé Quotidien (Simulation) :</strong>
- <strong>Discussions actives :</strong> 3 interlocuteurs aujourd'hui.
- <strong>Points clés :</strong> Karim a confirmé le point pour demain à 14h. La famille attend ta réponse pour le dîner.
- <strong>⚠️ Action requise :</strong> Valider la revue du document avec le contact d'ici ce soir.
    `;
  }
}

function closeDigest() {
  document.getElementById('digest-panel').style.display = 'none';
}

// Modal de connexion des comptes
function openConnectModal(platform) {
  currentTargetPlatform = platform;
  document.getElementById('modal-title').textContent = platform === 'facebook' ? 'Lier Facebook Messenger' : 'Lier Instagram DM';
  document.getElementById('connect-modal').style.display = 'flex';
}

function closeConnectModal() {
  document.getElementById('connect-modal').style.display = 'none';
}

function toggleLoginForm() {
  const method = document.getElementById('login-method').value;
  document.getElementById('form-credentials').style.display = method === 'credentials' ? 'block' : 'none';
  document.getElementById('form-cookies').style.display = method === 'cookies' ? 'block' : 'none';
}

async function submitAccountLogin() {
  const btn = document.getElementById('btn-submit-login');
  const status = document.getElementById('modal-status');
  btn.disabled = true;
  btn.textContent = 'Connexion au bridge en cours...';

  const method = document.getElementById('login-method').value;
  const payload = {
    platform: currentTargetPlatform,
    method: method,
    user: document.getElementById('login-user').value,
    pass: document.getElementById('login-pass').value,
    code_2fa: document.getElementById('login-2fa').value,
    cookies: document.getElementById('login-cookies').value
  };

  try {
    const res = await fetch('/api/bridge/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    if (res.ok) {
      status.style.display = 'block';
      status.style.color = '#4ade80';
      status.textContent = '✅ Compte lié avec succès au bridge local !';
      setTimeout(() => {
        closeConnectModal();
        checkPlatformStatus();
        loadConversations();
      }, 1500);
    } else {
      throw new Error("Échec de la validation");
    }
  } catch (e) {
    status.style.display = 'block';
    status.style.color = '#f87171';
    status.textContent = 'ℹ️ Requête envoyée au bridge. Vérifiez votre validation 2FA.';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Valider la connexion';
  }
}
