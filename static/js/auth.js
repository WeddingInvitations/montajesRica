import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js';
import {
  browserSessionPersistence,
  getAuth,
  GoogleAuthProvider,
  inMemoryPersistence,
  setPersistence,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signOut
} from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js';
import { firebaseConfig } from './firebase-config.js';

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const provider = new GoogleAuthProvider();
provider.setCustomParameters({ prompt: 'select_account' });

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
const button = document.getElementById('google-signin');
const errorNode = document.getElementById('auth-error');
const logoutButton = document.getElementById('logout-button');

function showError(message) {
  if (!errorNode) return;
  errorNode.textContent = message;
  errorNode.classList.remove('hidden');
}

async function establishServerSession(user) {
  const idToken = await user.getIdToken(true);
  const response = await fetch('/auth/session', {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrfToken
    },
    body: JSON.stringify({ idToken })
  });
  if (!response.ok) {
    await signOut(auth).catch(() => {});
    throw new Error('No se pudo validar la cuenta. Comprueba que has iniciado sesión con Google e inténtalo otra vez.');
  }
  await signOut(auth);
  window.location.replace(`${window.location.pathname}${window.location.hash}`);
}

if (button) {
  button.addEventListener('click', async () => {
    button.disabled = true;
    if (errorNode) errorNode.classList.add('hidden');
    try {
      const useRedirect = window.matchMedia('(max-width: 760px), (pointer: coarse)').matches;
      if (useRedirect) {
        await setPersistence(auth, browserSessionPersistence);
        await signInWithRedirect(auth, provider);
        return;
      }
      await setPersistence(auth, inMemoryPersistence);
      const result = await signInWithPopup(auth, provider);
      await establishServerSession(result.user);
    } catch (error) {
      console.error('Firebase sign-in failed:', error?.code || 'unknown');
      showError(error instanceof Error ? error.message : 'No se pudo iniciar sesión. Inténtalo otra vez.');
      button.disabled = false;
    }
  });
}

getRedirectResult(auth)
  .then((result) => result?.user ? establishServerSession(result.user) : undefined)
  .catch((error) => {
    console.error('Firebase redirect sign-in failed:', error?.code || 'unknown');
    showError('No se pudo completar el inicio de sesión con Google. Vuelve a intentarlo.');
  });

if (logoutButton) {
  logoutButton.addEventListener('click', async () => {
    logoutButton.disabled = true;
    try {
      await fetch('/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken }
      });
    } finally {
      await signOut(auth).catch(() => {});
      window.location.replace('/');
    }
  });
}
