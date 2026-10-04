import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";

function Login() {
  const navigate = useNavigate();
  const { login, register } = useAuth();

  const [isRegister, setIsRegister] =
    useState(false);

  const [form, setForm] = useState({
    full_name: "",
    email: "",
    role: "investigator",
    password: "",
    confirmPassword: "",
  });

  const [showPassword, setShowPassword] =
    useState(false);

  const [showConfirmPassword, setShowConfirmPassword] =
    useState(false);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  const [success, setSuccess] =
    useState("");

  const handleChange = (e) => {
    const { name, value } = e.target;

    setForm((previous) => ({
      ...previous,
      [name]: value,
    }));

    setError("");
    setSuccess("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    setError("");
    setSuccess("");

    if (!form.email || !form.password) {
      setError(
        "Please enter your email and password."
      );
      return;
    }

    if (isRegister) {
      if (!form.full_name.trim()) {
        setError("Please enter your full name.");
        return;
      }

      if (form.password.length < 6) {
        setError(
          "Password must contain at least 6 characters."
        );
        return;
      }

      if (
        form.password !==
        form.confirmPassword
      ) {
        setError(
          "Passwords do not match."
        );
        return;
      }
    }

    setLoading(true);

    try {
      if (isRegister) {
        await register({
          full_name:
            form.full_name.trim(),
          email:
            form.email.trim(),
          password:
            form.password,
          role:
            form.role,
        });

        setSuccess(
          "Account request submitted successfully. Please wait for administrator approval."
        );

        setForm({
          full_name: "",
          email: "",
          role: "investigator",
          password: "",
          confirmPassword: "",
        });
      } else {
        const result =
          await login(
            form.email.trim(),
            form.password
          );

        const role =
          result?.user?.role
            ?.toLowerCase();

        if (role === "admin") {
          navigate("/admin/dashboard");
        } else if (
          role === "approver"
        ) {
          navigate(
            "/approver/dashboard"
          );
        } else {
          navigate(
            "/investigator/dashboard"
          );
        }
      }
    } catch (err) {
      setError(
        err.message ||
          "Unable to complete the request."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#06110b] text-white flex">
      {/* LEFT SIDE */}

      <div className="hidden lg:flex lg:w-[55%] relative overflow-hidden bg-[#081b12]">
        <div className="absolute inset-0 opacity-30">
          <div
            className="absolute inset-0"
            style={{
              backgroundImage:
                "linear-gradient(rgba(80,190,110,0.16) 1px, transparent 1px), linear-gradient(90deg, rgba(80,190,110,0.16) 1px, transparent 1px)",
              backgroundSize: "50px 50px",
            }}
          />
        </div>

        <div className="absolute inset-0 bg-gradient-to-br from-emerald-950/70 via-transparent to-green-900/30" />

        <div className="relative z-10 flex flex-col justify-between w-full p-16">
          <div>
            {/* Logo */}

            <div className="flex items-center gap-3">
              <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-emerald-400 to-green-700 flex items-center justify-center text-xl font-bold text-[#06110b] shadow-lg shadow-emerald-500/20">
                O
              </div>

              <span className="text-2xl font-bold tracking-tight">
                One<span className="text-emerald-400">
                  Recon
                </span>
              </span>
            </div>

            {/* Hero */}

            <div className="mt-20">
              <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 text-sm font-medium">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                Intelligent Reconciliation Platform
              </div>

              <h1 className="mt-8 text-6xl font-bold leading-[1.05] tracking-tight">
                Reconcile.
                <br />

                <span className="bg-gradient-to-r from-emerald-300 to-lime-300 bg-clip-text text-transparent">
                  Resolve.
                </span>

                <br />

                Reimagine.
              </h1>

              <p className="mt-8 max-w-xl text-lg leading-8 text-slate-400">
                A unified platform for intelligent
                transaction reconciliation,
                automated break investigation,
                and real-time financial insights.
              </p>
            </div>

            {/* Feature Cards */}

            <div className="mt-10 grid grid-cols-3 gap-3 max-w-2xl">
              <FeatureCard
                icon="↔"
                title="Smart Matching"
                subtitle="Automated"
              />

              <FeatureCard
                icon="◇"
                title="AI Analysis"
                subtitle="Intelligent"
              />

              <FeatureCard
                icon="✓"
                title="Audit Ready"
                subtitle="Traceable"
              />
            </div>
          </div>

          <div className="flex justify-between text-xs text-slate-500">
            <span>
              Secure financial operations
            </span>

            <span>
              OneRecon © 2026
            </span>
          </div>
        </div>
      </div>

      {/* RIGHT SIDE */}

      <div className="flex-1 flex items-center justify-center px-6 py-12 bg-[#06110b]">
        <div className="w-full max-w-[475px]">
          <div className="rounded-3xl border border-emerald-900/50 bg-[#0c1711] p-8 md:p-10 shadow-2xl shadow-black/40">
            {/* Heading */}

            <div className="mb-8">
              <p className="text-sm font-semibold text-emerald-400 uppercase tracking-wide">
                {isRegister
                  ? "Request Access"
                  : "Welcome Back"}
              </p>

              <h2 className="mt-2 text-3xl font-bold">
                {isRegister
                  ? "Create your account"
                  : "Sign in to OneRecon"}
              </h2>

              <p className="mt-2 text-sm text-slate-400">
                {isRegister
                  ? "Submit your details for administrator approval"
                  : "Access your reconciliation workspace"}
              </p>
            </div>

            {/* Error */}

            {error && (
              <div className="mb-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
                {error}
              </div>
            )}

            {/* Success */}

            {success && (
              <div className="mb-5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-400">
                {success}
              </div>
            )}

            <form
              onSubmit={handleSubmit}
              className="space-y-5"
            >
              {/* Full Name */}

              {isRegister && (
                <Input
                  label="Full Name"
                  name="full_name"
                  value={form.full_name}
                  onChange={handleChange}
                  placeholder="Enter your full name"
                />
              )}

              {/* Email */}

              <Input
                label="Email address"
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                placeholder="Enter your email"
              />

              {/* Role */}

              {isRegister && (
                <div>
                  <label className="block mb-2 text-xs font-semibold text-slate-300">
                    Requested Role
                  </label>

                  <select
                    name="role"
                    value={form.role}
                    onChange={handleChange}
                    className="w-full rounded-xl border border-emerald-950 bg-[#101f17] px-4 py-3 text-sm text-white outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
                  >
                    <option value="investigator">
                      Investigator
                    </option>

                    <option value="approver">
                      Approver
                    </option>
                  </select>

                  <p className="mt-2 text-xs text-slate-500">
                    Your requested role will be reviewed
                    by an administrator.
                  </p>
                </div>
              )}

              {/* Password */}

              <PasswordInput
                label="Password"
                name="password"
                value={form.password}
                onChange={handleChange}
                placeholder="Enter your password"
                visible={showPassword}
                onToggle={() =>
                  setShowPassword(
                    (value) => !value
                  )
                }
              />

              {/* Confirm Password */}

              {isRegister && (
                <PasswordInput
                  label="Confirm Password"
                  name="confirmPassword"
                  value={
                    form.confirmPassword
                  }
                  onChange={handleChange}
                  placeholder="Confirm your password"
                  visible={
                    showConfirmPassword
                  }
                  onToggle={() =>
                    setShowConfirmPassword(
                      (value) => !value
                    )
                  }
                />
              )}

              {/* Submit */}

              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-gradient-to-r from-emerald-500 to-green-600 px-5 py-3.5 text-sm font-bold text-[#06110b] shadow-lg shadow-emerald-600/20 transition hover:from-emerald-400 hover:to-green-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading
                  ? isRegister
                    ? "Submitting..."
                    : "Signing in..."
                  : isRegister
                    ? "Request Access"
                    : "Sign In"}
              </button>
            </form>

            {/* Switch */}

            <div className="mt-7 border-t border-white/10 pt-6 text-center">
              {isRegister ? (
                <>
                  <p className="text-sm text-slate-500">
                    Already have an account?
                  </p>

                  <button
                    type="button"
                    onClick={() => {
                      setIsRegister(false);
                      setError("");
                      setSuccess("");
                    }}
                    className="mt-2 text-sm font-semibold text-emerald-400 hover:text-emerald-300"
                  >
                    ← Back to Sign In
                  </button>
                </>
              ) : (
                <>
                  <p className="text-sm text-slate-500">
                    Don't have an account?
                  </p>

                  <button
                    type="button"
                    onClick={() => {
                      setIsRegister(true);
                      setError("");
                      setSuccess("");
                    }}
                    className="mt-2 text-sm font-semibold text-emerald-400 hover:text-emerald-300"
                  >
                    Request access →
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureCard({
  icon,
  title,
  subtitle,
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4">
      <div className="mb-4 flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
        {icon}
      </div>

      <p className="text-sm font-semibold text-slate-200">
        {title}
      </p>

      <p className="mt-1 text-xs text-slate-500">
        {subtitle}
      </p>
    </div>
  );
}

function Input({
  label,
  name,
  type = "text",
  value,
  onChange,
  placeholder,
}) {
  return (
    <div>
      <label className="mb-2 block text-xs font-semibold text-slate-300">
        {label}
      </label>

      <input
        type={type}
        name={name}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={
          type === "email"
            ? "email"
            : "name"
        }
        className="w-full rounded-xl border border-emerald-950 bg-[#101f17] px-4 py-3 text-sm text-white outline-none placeholder:text-slate-600 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
      />
    </div>
  );
}

function PasswordInput({
  label,
  name,
  value,
  onChange,
  placeholder,
  visible,
  onToggle,
}) {
  return (
    <div>
      <label className="mb-2 block text-xs font-semibold text-slate-300">
        {label}
      </label>

      <div className="relative">
        <input
          type={
            visible
              ? "text"
              : "password"
          }
          name={name}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          autoComplete={
            name === "password"
              ? "current-password"
              : "new-password"
          }
          className="w-full rounded-xl border border-emerald-950 bg-[#101f17] px-4 py-3 pr-16 text-sm text-white outline-none placeholder:text-slate-600 transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20"
        />

        <button
          type="button"
          onClick={onToggle}
          className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-slate-500 hover:text-slate-300"
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
    </div>
  );
}

export default Login;