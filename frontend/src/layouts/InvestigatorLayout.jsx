import { Outlet, useLocation, useNavigate } from "react-router-dom";

function InvestigatorLayout() {
  const navigate = useNavigate();
  const location = useLocation();

  const navigation = [
    {
      label: "Dashboard",
      path: "/investigator/dashboard",
      icon: "⌂",
    },
    {
      label: "Mapping",
      path: "/investigator/mapping",
      icon: "◇",
    },
    {
      label: "Breaks",
      path: "/investigator/breaks",
      icon: "⚠",
    },
    {
      label: "Evidence",
      path: "/investigator/evidence",
      icon: "▣",
    },
  ];

  const isActive = (path) => {
    if (path === "/investigator/dashboard") {
      return location.pathname === path;
    }

    return location.pathname.startsWith(path);
  };

  const handleLogout = () => {
    localStorage.removeItem("user");
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-[#03130f] text-white relative overflow-hidden">

      {/* =====================================================
          BACKGROUND GRID
      ====================================================== */}

      <div
        className="fixed inset-0 pointer-events-none opacity-30"
        style={{
          backgroundImage: `
            linear-gradient(
              rgba(38, 180, 126, 0.07) 1px,
              transparent 1px
            ),
            linear-gradient(
              90deg,
              rgba(38, 180, 126, 0.07) 1px,
              transparent 1px
            )
          `,
          backgroundSize: "48px 48px",
        }}
      />

      {/* =====================================================
          SIDEBAR
      ====================================================== */}

      <aside className="fixed left-0 top-0 z-50 h-screen w-64 bg-[#061711]/95 backdrop-blur-xl border-r border-[#12382c]">

        <div className="flex h-full flex-col">

          {/* -------------------------------------------------
              LOGO
          -------------------------------------------------- */}

          <div className="px-6 pt-7 pb-6">

            <button
              onClick={() => navigate("/investigator/dashboard")}
              className="flex items-center gap-3"
            >

              {/* Logo */}
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-[#23d68a] to-[#0c9e5e] shadow-lg shadow-green-950/40">
                <span className="text-xl font-black text-[#032117]">
                  O
                </span>
              </div>

              {/* Brand */}
              <div className="text-xl font-bold tracking-tight">
                One<span className="text-[#28d995]">Recon</span>
              </div>

            </button>

          </div>

          {/* -------------------------------------------------
              ROLE
          -------------------------------------------------- */}

          <div className="mx-5 mb-6 rounded-xl border border-[#164b38] bg-[#0a2119] px-4 py-3">

            <div className="text-[10px] uppercase tracking-[0.18em] text-[#5b8d7a]">
              Workspace
            </div>

            <div className="mt-1 flex items-center gap-2">

              <span className="h-2 w-2 rounded-full bg-[#27d98b] shadow-[0_0_8px_#27d98b]" />

              <span className="text-sm font-medium text-[#d7f5e9]">
                Investigator
              </span>

            </div>

          </div>

          {/* -------------------------------------------------
              NAVIGATION
          -------------------------------------------------- */}

          <div className="px-4">

            <p className="px-3 mb-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#527566]">
              Workspace
            </p>

            <nav className="space-y-1">

              {navigation.map((item) => {
                const active = isActive(item.path);

                return (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    className={`
                      group relative flex w-full items-center gap-3
                      rounded-xl px-3 py-3 text-left text-sm
                      transition-all duration-200
                      ${
                        active
                          ? "bg-[#0d3023] text-[#39e29a]"
                          : "text-[#7fa394] hover:bg-[#0a241b] hover:text-[#d9f7ea]"
                      }
                    `}
                  >

                    {/* Active indicator */}
                    {active && (
                      <span className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r-full bg-[#28d995]" />
                    )}

                    {/* Icon */}
                    <span
                      className={`
                        flex h-8 w-8 items-center justify-center
                        rounded-lg text-base
                        ${
                          active
                            ? "bg-[#123d2c] text-[#36dc97]"
                            : "bg-[#0a2119] text-[#668c7d] group-hover:text-[#36dc97]"
                        }
                      `}
                    >
                      {item.icon}
                    </span>

                    <span className="font-medium">
                      {item.label}
                    </span>

                  </button>
                );
              })}

            </nav>

          </div>

          {/* -------------------------------------------------
              INVESTIGATION QUICK ACCESS
          -------------------------------------------------- */}

          <div className="mx-5 mt-6 border-t border-[#12382c] pt-5">

            <p className="mb-3 px-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-[#527566]">
              Investigation
            </p>

            <button
              onClick={() => navigate("/investigator/breaks")}
              className={`
                flex w-full items-center gap-3 rounded-xl px-3 py-3
                text-left text-sm transition
                ${
                  location.pathname.startsWith(
                    "/investigator/investigation"
                  )
                    ? "bg-[#0d3023] text-[#39e29a]"
                    : "text-[#7fa394] hover:bg-[#0a241b] hover:text-[#d9f7ea]"
                }
              `}
            >

              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#0a2119]">
                ⌕
              </span>

              <span>
                Investigations
              </span>

            </button>

          </div>

          {/* -------------------------------------------------
              BOTTOM USER SECTION
          -------------------------------------------------- */}

          <div className="mt-auto border-t border-[#12382c] p-4">

            <div className="mb-3 flex items-center gap-3 rounded-xl bg-[#081e16] px-3 py-3">

              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-[#27d98b] to-[#087b4a] text-sm font-bold text-[#032117]">
                I
              </div>

              <div className="min-w-0">

                <p className="truncate text-sm font-medium text-white">
                  Investigator
                </p>

                <p className="truncate text-xs text-[#608677]">
                  Investigator User
                </p>

              </div>

            </div>

            <button
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-3 text-sm text-[#77998c] transition hover:bg-[#1d1414] hover:text-red-400"
            >

              <span className="text-base">
                ↪
              </span>

              Logout

            </button>

          </div>

        </div>

      </aside>

      {/* =====================================================
          MAIN CONTENT
      ====================================================== */}

      <div className="relative min-h-screen pl-64">

        {/* -------------------------------------------------
            TOP BAR
        -------------------------------------------------- */}

        <header className="sticky top-0 z-40 flex h-20 items-center justify-between border-b border-[#12382c] bg-[#03130f]/90 px-8 backdrop-blur-xl">

          <div>

            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[#4f806e]">
              OneRecon
            </p>

            <h1 className="mt-1 text-lg font-semibold text-white">
              Investigator Workspace
            </h1>

          </div>

          <div className="flex items-center gap-4">

            {/* System status */}
            <div className="hidden items-center gap-2 rounded-full border border-[#164b38] bg-[#081f17] px-3 py-2 sm:flex">

              <span className="h-2 w-2 rounded-full bg-[#27d98b] shadow-[0_0_7px_#27d98b]" />

              <span className="text-xs text-[#79a697]">
                System Operational
              </span>

            </div>

            {/* Role */}
            <div className="rounded-lg border border-[#164b38] bg-[#081f17] px-3 py-2 text-xs text-[#63a48e]">
              INVESTIGATOR
            </div>

          </div>

        </header>

        {/* -------------------------------------------------
            PAGE CONTENT
        -------------------------------------------------- */}

        <main className="relative p-6 lg:p-8">

          <Outlet />

        </main>

      </div>

    </div>
  );
}

export default InvestigatorLayout;