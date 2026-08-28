import { api, el, toast, getToken, isAuthed, getUser, setUser } from './utils.js?v=47';
import { openLogin } from './auth.js?v=47';

function loadRazorpay(key) {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) return resolve();
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Could not load Razorpay'));
    document.body.appendChild(s);
  });
}

export function initPremium() {
  const payBtn = el('premium-pay');
  if (payBtn) payBtn.addEventListener('click', startCheckout);

  document.querySelectorAll('a, button').forEach((b) => {
    if (/upgrade|unlimited|trial/i.test(b.textContent || '')) {
      b.addEventListener('click', (e) => {
        if (b.closest('.modal')) return;
        e.preventDefault();
        if (!isAuthed()) { openLogin(); return; }
        import('./utils.js').then((m) => m.openModal('premium-modal'));
      });
    }
  });
}

function activatePremiumDemo() {
  const u = getUser() || {};
  u.premium = true;
  setUser(u);
  const q = el('veda-quota');
  if (q) q.textContent = 'Unlimited questions';
  const badge = el('profile-badge');
  if (badge) badge.style.display = '';
  const sub = el('sub-label');
  if (sub) sub.textContent = 'Pro ⚡';
  const st = el('premium-status');
  if (st) { st.textContent = '✓ Premium activated (demo mode — add Razorpay keys for real payments).'; st.style.color = 'var(--green)'; }
  toast('Premium activated (demo mode). Enjoy unlimited Veda!', 'ok');
}

function startCheckout() {
  if (!isAuthed()) { toast('Please log in first.', 'info'); openLogin(); return; }
  const u = getUser() || {};
  if (u.premium) {
    const st = el('premium-status');
    if (st) { st.textContent = 'You are already a Premium member.'; st.style.color = 'var(--green)'; }
    return;
  }
  const status = el('premium-status');
  status.textContent = 'Creating order…';
  status.style.color = 'var(--sub)';

  api('/premium/checkout', { method: 'POST', body: JSON.stringify({ user_id: 'me', plan: 'pro_monthly' }) })
    .then((data) => {
      if (!data || !data.order_id || !data.key) {
        activatePremiumDemo();
        return;
      }
      loadRazorpay(data.key).then(() => {
        const rzp = new window.Razorpay({
          key: data.key,
          amount: data.amount * 100,
          currency: data.currency || 'INR',
          name: 'Learnify Premium',
          description: 'Pro Monthly',
          order_id: data.order_id,
          handler: () => {
            const u2 = getUser() || {}; u2.premium = true; setUser(u2);
            if (el('profile-badge')) el('profile-badge').style.display = '';
            if (el('sub-label')) el('sub-label').textContent = 'Pro ⚡';
            if (el('veda-quota')) el('veda-quota').textContent = 'Unlimited questions';
            status.textContent = '✓ Payment successful. Welcome to Premium!';
            status.style.color = 'var(--green)';
          },
          modal: { ondismiss: () => { status.textContent = 'Payment cancelled.'; status.style.color = 'var(--sub)'; } }
        });
        rzp.open();
      }).catch(() => activatePremiumDemo());
    })
    .catch((err) => {
      if (err.message && (err.message.includes('503') || /enabled|razorpay/i.test(err.message))) {
        activatePremiumDemo();
      } else {
        status.textContent = err.message;
        status.style.color = '#c0392b';
      }
    });
}
