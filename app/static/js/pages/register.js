import { ApiError, userMessage } from "../api.js";
import { register, signIn } from "../auth.js";
import { navigate } from "../router.js";
import { authScreen } from "../ui/auth-screen.js";
import { h } from "../ui/dom.js";
import { EMAIL_RE, bindSubmit, errorSlot, field } from "../ui/form.js";

export default function registerPage() {
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
    autocomplete: "new-password",
    hint: "At least 8 characters.",
  });
  const errors = errorSlot();
  const submit = h(
    "button",
    { type: "submit", class: "btn btn--primary" },
    "Create account",
  );

  const form = h(
    "form",
    { class: "form", novalidate: true },
    errors.node,
    email.root,
    password.root,
    submit,
  );

  bindSubmit(form, submit, "Creating account…", async () => {
    errors.clear();
    const emailValue = email.input.value.trim();
    const passwordValue = password.input.value;

    const emailError = EMAIL_RE.test(emailValue)
      ? ""
      : "Enter a valid email address.";
    let passwordError = "";
    if (passwordValue.length < 8) passwordError = "Use at least 8 characters.";
    else if (passwordValue.length > 128)
      passwordError = "Use 128 characters or fewer.";

    email.setError(emailError);
    password.setError(passwordError);
    if (emailError || passwordError) {
      (emailError ? email : password).input.focus();
      return;
    }

    try {
      await register(emailValue, passwordValue);
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        email.setError("That email is already registered. Sign in instead.");
        email.input.focus();
      } else {
        errors.show(userMessage(error));
      }
      return;
    }

    try {
      await signIn(emailValue, passwordValue);
    } catch {
      errors.show(
        "Your account was created, but signing in failed. Try signing in.",
      );
      return;
    }
    navigate("/documents", { replace: true });
  });

  return {
    title: "Create an account",
    node: authScreen({
      title: "Create an account",
      form,
      footer: [
        "Already have an account? ",
        h("a", { href: "#/login" }, "Sign in"),
      ],
    }),
    focus: email.input,
  };
}
