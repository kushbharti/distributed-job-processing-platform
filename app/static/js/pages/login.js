import { userMessage } from "../api.js";
import { signIn } from "../auth.js";
import { navigate } from "../router.js";
import { authScreen } from "../ui/auth-screen.js";
import { h } from "../ui/dom.js";
import { EMAIL_RE, bindSubmit, errorSlot, field } from "../ui/form.js";

// Only allow in-app destinations, so a crafted link can't send people elsewhere.
function safeNext(value) {
  return value && /^\/[A-Za-z0-9/_-]*$/.test(value) ? value : "/documents";
}

export default function loginPage({ query }) {
  const email = field({
    id: "email",
    label: "Email",
    type: "email",
    autocomplete: "username",
    attrs: { autocapitalize: "none", spellcheck: "false" },
  });
  const password = field({
    id: "password",
    label: "Password",
    type: "password",
    autocomplete: "current-password",
  });
  const errors = errorSlot();
  const submit = h(
    "button",
    { type: "submit", class: "btn btn--primary" },
    "Sign in",
  );

  const form = h(
    "form",
    { class: "form", novalidate: true },
    query.has("expired") &&
      h(
        "p",
        { class: "notice notice--info" },
        "Your session ended. Sign in again to continue.",
      ),
    errors.node,
    email.root,
    password.root,
    submit,
  );

  bindSubmit(form, submit, "Signing in…", async () => {
    errors.clear();
    const emailValue = email.input.value.trim();
    const passwordValue = password.input.value;

    const emailError = EMAIL_RE.test(emailValue)
      ? ""
      : "Enter a valid email address.";
    const passwordError = passwordValue ? "" : "Enter your password.";
    email.setError(emailError);
    password.setError(passwordError);
    if (emailError || passwordError) {
      (emailError ? email : password).input.focus();
      return;
    }

    try {
      await signIn(emailValue, passwordValue);
    } catch (error) {
      errors.show(userMessage(error));
      return;
    }
    navigate(safeNext(query.get("next")), { replace: true });
  });

  return {
    title: "Sign in",
    node: authScreen({
      title: "Sign in",
      form,
      footer: [
        "New here? ",
        h("a", { href: "#/register" }, "Create an account"),
      ],
    }),
    focus: email.input,
  };
}
