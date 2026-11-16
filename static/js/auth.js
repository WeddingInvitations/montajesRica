import { initializeApp } from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-app.js';
import {
  browserSessionPersistence,
  createUserWithEmailAndPassword,
  EmailAuthProvider,
  getAdditionalUserInfo,
  getAuth,
  GoogleAuthProvider,
  inMemoryPersistence,
  linkWithCredential,
  sendEmailVerification,
  sendPasswordResetEmail,
  setPersistence,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
  getRedirectResult,
  signOut
} from 'https://www.gstatic.com/firebasejs/11.10.0/firebase-auth.js';
import { firebaseConfig } from './firebase-config.js';

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content || '';
const googleButton = document.getElementById('google-signin');
const emailForm = document.getElementById('email-auth-form');
const emailInput = document.getElementById('auth-email');
const passwordInput = document.getElementById('auth-password');
const confirmWrap = document.getElementById('confirm-password-wrap');
const confirmInput = document.getElementById('auth-password-confirm');
const emailSubmit = document.getElementById('email-submit');
const toggleRegister = document.getElementById('toggle-register');
const forgotPassword = document.getElementById('forgot-password');
const passwordSetup = document.getElementById('google-password-setup');
const passwordSetupForm = document.getElementById('google-password-form');
const passwordSetupInput = document.getElementById('google-password');
const passwordSetupConfirm = document.getElementById('google-password-confirm');
const savePasswordButton = document.getElementById('save-google-password');
const cancelPasswordButton = document.getElementById('cancel-google-password');
const errorNode = document.getElementById('auth-error');
const logoutButton = document.getElementById('logout-button');
let registering = false;
let pendingGoogleUser = null;

function showMessage(message, kind = 'error') {
  if (!errorNode) return;
  errorNode.textContent = message;
  errorNode.classList.toggle('auth-error', kind === 'error');
  errorNode.classList.toggle('auth-success', kind === 'success');
  errorNode.classList.remove('hidden');
}

function clearMessage() {
  errorNode?.classList.add('hidden');
}

function friendlyAuthError(error) {
  if (error?.stage === 'session-exchange') {
    if (error.status === 503) {
      return error.backendMessage || 'Google autenticó la cuenta, pero el servidor no tiene permisos para consultar Firebase Auth/Firestore. Para desarrollo local, configura ADC con una cuenta autorizada; en App Engine, revisa los roles de la cuenta de servicio.';
    }
    return `Google te autenticó, pero el servidor no pudo crear la sesión (HTTP ${error.status || 'desconocido'}). En desarrollo local, comprueba que las credenciales ADC de Google tienen permisos en Firestore y Firebase Authentication.`;
  }
  const messages = {
    'auth/configuration-not-found': 'Firebase Authentication aún no está inicializado en montajesrica. En Firebase Console abre Authentication y pulsa “Comenzar”.',
    'auth/unauthorized-domain': 'Este dominio no está autorizado. Añade localhost, 127.0.0.1 y montajesrica.ew.r.appspot.com en Authentication → Configuración → Dominios autorizados.',
    'auth/operation-not-allowed': 'Habilita Google y Correo/contraseña en Firebase Console → Authentication → Método de acceso.',
    'auth/popup-blocked': 'El navegador bloqueó la ventana de Google. Permite ventanas emergentes o vuelve a intentarlo.',
    'auth/email-already-in-use': 'Ese correo ya tiene una cuenta. Inicia sesión con ella o usa “¿Olvidaste la contraseña?”.',
    'auth/weak-password': 'La contraseña debe tener al menos 6 caracteres.',
    'auth/invalid-email': 'Introduce un correo electrónico válido.',
    'auth/invalid-credential': 'No coinciden el correo y la contraseña. Comprueba los datos o restablece la contraseña.',
    'auth/wrong-password': 'La contraseña no es correcta. Puedes restablecerla desde el enlace correspondiente.',
    'auth/user-not-found': 'No hay una cuenta con ese correo. Selecciona “Crear una cuenta” para registrarte.',
    'auth/account-exists-with-different-credential': 'Ya existe una cuenta con ese correo. Entra con su método actual y vincula Google desde esa cuenta.'
  };
  return messages[error?.code] || 'No se pudo completar la autenticación. Revisa los datos e inténtalo otra vez.';
}

function setBusy(isBusy) {
  [googleButton, emailSubmit, toggleRegister, forgotPassword, savePasswordButton, cancelPasswordButton].forEach((button) => {
    if (button) button.disabled = isBusy;
  });
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
    let backendMessage = '';
    try {
      const body = await response.json();
      backendMessage = body.description || body.message || '';
    } catch {
      // Keep the generic message if the server response is not JSON.
    }
    await signOut(auth).catch(() => {});
    const error = new Error('El backend rechazó el intercambio de sesión.');
    error.stage = 'session-exchange';
    error.status = response.status;
    error.backendMessage = backendMessage;
    throw error;
  }
  await signOut(auth);
  window.location.replace(`${window.location.pathname}${window.location.hash}`);
}

function showGooglePasswordSetup(user) {
  pendingGoogleUser = user;
  if (googleButton) googleButton.classList.add('hidden');
  emailForm?.classList.add('hidden');
  document.querySelector('.auth-divider')?.classList.add('hidden');
  passwordSetup?.classList.remove('hidden');
  if (emailInput && user.email) emailInput.value = user.email;
  passwordSetupInput?.focus();
}

async function cancelGooglePasswordSetup() {
  pendingGoogleUser = null;
  await signOut(auth).catch(() => {});
  passwordSetup?.classList.add('hidden');
  googleButton?.classList.remove('hidden');
  emailForm?.classList.remove('hidden');
  document.querySelector('.auth-divider')?.classList.remove('hidden');
  passwordSetupForm?.reset();
  clearMessage();
}

async function finishGoogleSignIn(user) {
  const hasPassword = user.providerData.some((provider) => provider.providerId === 'password');
  if (!hasPassword) {
    showGooglePasswordSetup(user);
    return;
  }
  await establishServerSession(user);
}

if (googleButton) {
  googleButton.addEventListener('click', async () => {
    clearMessage();
    setBusy(true);
    let stage = 'google-popup';
    try {
      const useRedirect = window.matchMedia('(max-width: 760px), (pointer: coarse)').matches;
      if (useRedirect) {
        await setPersistence(auth, browserSessionPersistence);
        await signInWithRedirect(auth, googleProvider);
        return;
      }
      await setPersistence(auth, inMemoryPersistence);
      const result = await signInWithPopup(auth, googleProvider);
      const additionalInfo = getAdditionalUserInfo(result);
      if (additionalInfo?.isNewUser || !result.user.providerData.some((provider) => provider.providerId === 'password')) {
        showGooglePasswordSetup(result.user);
      } else {
        stage = 'session-exchange';
        await finishGoogleSignIn(result.user);
      }
    } catch (error) {
      console.error('Firebase Google sign-in failed:', {
        stage: error?.stage || stage,
        code: error?.code || 'unknown',
        name: error?.name || 'Error',
        message: error?.message || 'No message'
      });
      showMessage(friendlyAuthError(error));
    } finally {
      setBusy(false);
    }
  });
}

if (emailForm) {
  emailForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearMessage();
    if (registering && passwordInput.value !== confirmInput.value) {
      showMessage('Las contraseñas no coinciden.');
      confirmInput.focus();
      return;
    }

    setBusy(true);
    try {
      await setPersistence(auth, inMemoryPersistence);
      if (registering) {
        const credential = await createUserWithEmailAndPassword(auth, emailInput.value.trim(), passwordInput.value);
        await sendEmailVerification(credential.user);
        await signOut(auth);
        emailForm.reset();
        setRegistrationMode(false);
        showMessage('Te enviamos un correo para verificar la cuenta. Confirma la dirección y luego inicia sesión.', 'success');
      } else {
        const credential = await signInWithEmailAndPassword(auth, emailInput.value.trim(), passwordInput.value);
        if (!credential.user.emailVerified) {
          await sendEmailVerification(credential.user).catch(() => {});
          await signOut(auth);
          showMessage('Tu correo aún no está verificado. Te enviamos otro enlace; confírmalo y vuelve a entrar.');
          return;
        }
        await establishServerSession(credential.user);
      }
    } catch (error) {
      console.error('Firebase email sign-in failed:', error?.code || 'unknown');
      showMessage(friendlyAuthError(error));
    } finally {
      setBusy(false);
    }
  });
}

function setRegistrationMode(enabled) {
  registering = enabled;
  if (confirmWrap) confirmWrap.classList.toggle('hidden', !enabled);
  if (confirmInput) confirmInput.required = enabled;
  if (passwordInput) passwordInput.autocomplete = enabled ? 'new-password' : 'current-password';
  if (emailSubmit) emailSubmit.textContent = enabled ? 'Crear cuenta' : 'Iniciar sesión';
  if (toggleRegister) toggleRegister.textContent = enabled ? 'Ya tengo una cuenta' : 'Crear una cuenta';
  if (forgotPassword) forgotPassword.classList.toggle('hidden', enabled);
  clearMessage();
}

toggleRegister?.addEventListener('click', () => setRegistrationMode(!registering));

forgotPassword?.addEventListener('click', async () => {
  clearMessage();
  const email = emailInput?.value.trim();
  if (!email) {
    showMessage('Escribe tu correo y vuelve a pulsar “¿Olvidaste la contraseña?”.');
    emailInput?.focus();
    return;
  }
  setBusy(true);
  try {
    await sendPasswordResetEmail(auth, email);
    showMessage('Si hay una cuenta asociada a ese correo, recibirás un enlace para restablecer la contraseña.', 'success');
  } catch (error) {
    console.error('Firebase password reset failed:', error?.code || 'unknown');
    showMessage(friendlyAuthError(error));
  } finally {
    setBusy(false);
  }
});

cancelPasswordButton?.addEventListener('click', cancelGooglePasswordSetup);

passwordSetupForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearMessage();
  if (!pendingGoogleUser) {
    showMessage('Vuelve a iniciar sesión con Google para configurar tu contraseña.');
    return;
  }
  if (passwordSetupInput.value !== passwordSetupConfirm.value) {
    showMessage('Las contraseñas no coinciden.');
    passwordSetupConfirm.focus();
    return;
  }
  setBusy(true);
  try {
    const email = pendingGoogleUser.email;
    if (!email) throw new Error('La cuenta de Google no tiene correo asociado.');
    const credential = EmailAuthProvider.credential(email, passwordSetupInput.value);
    const linked = await linkWithCredential(pendingGoogleUser, credential);
    pendingGoogleUser = null;
    await establishServerSession(linked.user);
  } catch (error) {
    console.error('Firebase password linking failed:', error?.code || 'unknown');
    showMessage(friendlyAuthError(error));
  } finally {
    setBusy(false);
  }
});

getRedirectResult(auth)
  .then((result) => result?.user ? finishGoogleSignIn(result.user) : undefined)
  .catch((error) => {
    console.error('Firebase redirect sign-in failed:', error?.code || 'unknown');
    showMessage(friendlyAuthError(error));
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
