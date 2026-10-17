"""
Draws a clean, high-resolution, professional diagram for Slide 11:
'Chaos Stress-Testing & Evaluation Protocol'
- Column 1: Controlled Fault Injection Catalog (SCN-01 to SCN-04)
- Column 2: Safety Isolation & Blast Radius Boundaries
- Column 3: Comparative Evaluation Harness & Metric Definitions (MTTR, MTTD, Accuracy)
- Clean Minimalist Professional Palette matching the presentation theme.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_chaos_protocol_diagram(output_png="chaos_evaluation_protocol_model.png"):
    fig, ax = plt.subplots(figsize=(16, 9), dpi=300)
    ax.set_facecolor("#FFFFFF")
    fig.patch.set_facecolor("#FFFFFF")

    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)

    # Color Palette
    C_DARK = "#0F172A"          # Dark Slate
    C_MUTED = "#64748B"         # Slate 500
    C_PRIMARY = "#1D4ED8"       # Cobalt Blue
    C_ACCENT_RED = "#DC2626"    # Crimson for Chaos
    C_ACCENT_PURPLE = "#7C3AED" # Purple for Safety Guardrails
    C_ACCENT_TEAL = "#0D9488"   # Teal for Metrics
    C_ARROW = "#334155"         # Slate 700

    # Main Title & Subtitle Banner
    ax.text(
        50, 97.2, "Experimental Protocol: Chaos Stress-Testing & Evaluation Harness",
        ha="center", va="center",
        fontsize=16.5, fontweight="bold", color=C_DARK, fontname="DejaVu Sans"
    )
    ax.text(
        50, 93.8, "Standardized Fault Injection Catalog, Safety Isolation Boundaries, and Quantitative Benchmarking Methodology",
        ha="center", va="center",
        fontsize=10.2, color="#475569", fontname="DejaVu Sans"
    )

    # 3 MAIN COLUMNS / SECTIONS
    col_w = 28.5
    col_h = 74.0
    col_y = 13.5

    # ==========================================
    # --- COLUMN 1: FAULT INJECTION CATALOG ---
    # ==========================================
    col1_x = 3.5

    pill1 = patches.FancyBboxPatch(
        (col1_x, col_y + col_h + 1.2), col_w, 3.6,
        boxstyle="round,pad=0.5,rounding_size=1.2",
        facecolor=C_ACCENT_RED,
        edgecolor=C_ACCENT_RED,
        linewidth=1.0,
        zorder=3
    )
    ax.add_patch(pill1)
    ax.text(
        col1_x + col_w / 2, col_y + col_h + 3.0, "1. FAULT INJECTION CATALOG",
        ha="center", va="center",
        fontsize=9.2, fontweight="bold", color="#FFFFFF",
        fontname="DejaVu Sans", zorder=4
    )

    card1 = patches.FancyBboxPatch(
        (col1_x, col_y), col_w, col_h,
        boxstyle="round,pad=0.8,rounding_size=2.0",
        facecolor="#FEF2F2",
        edgecolor=C_ACCENT_RED,
        linewidth=1.8,
        zorder=2
    )
    ax.add_patch(card1)

    ax.text(
        col1_x + col_w / 2, col_y + col_h - 3.8, "Standardized Fault Catalog",
        ha="center", va="center",
        fontsize=12.0, fontweight="bold", color="#991B1B",
        fontname="DejaVu Sans", zorder=3
    )

    scenarios = [
        ("SCN-01: Defective Rollout", "CrashLoopBackOff", "Injects broken application image;\ncauses startup crash & non-zero exit code."),
        ("SCN-02: Configuration Drift", "Out-of-Band Divergence", "Mutates live container environment variables\ndiverging silently from declarative Git repo."),
        ("SCN-03: Latency Regression", "Performance Anomaly", "Applies artificial 800ms processing delay\nand synthetic 500 error spikes post-deploy."),
        ("SCN-04: Ambiguous Spike", "HITL Gating Validation", "Simulates external traffic load surge without\ndeploy to verify human operator escalation.")
    ]

    sc_y = col_y + col_h - 7.5
    for s_title, s_type, s_desc in scenarios:
        sc_box = patches.FancyBboxPatch(
            (col1_x + 1.2, sc_y - 14.2), col_w - 2.4, 13.8,
            boxstyle="round,pad=0.5,rounding_size=1.2",
            facecolor="#FFFFFF",
            edgecolor="#FCA5A5",
            linewidth=1.2,
            zorder=3
        )
        ax.add_patch(sc_box)

        ax.text(
            col1_x + 2.2, sc_y - 2.8, s_title,
            ha="left", va="center",
            fontsize=9.5, fontweight="bold", color="#7F1D1D",
            fontname="DejaVu Sans", zorder=4
        )
        ax.text(
            col1_x + 2.2, sc_y - 5.5, f"Class: {s_type}",
            ha="left", va="center",
            fontsize=8.5, fontweight="bold", color=C_ACCENT_RED,
            fontname="DejaVu Sans", zorder=4
        )
        ax.text(
            col1_x + 2.2, sc_y - 9.8, s_desc,
            ha="left", va="center",
            fontsize=8.0, color="#475569",
            fontname="DejaVu Sans", zorder=4
        )
        sc_y -= 15.6

    # Connecting Arrow 1 -> 2
    ax.annotate(
        "", xy=(35.5, 50.5), xytext=(32.5, 50.5),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=2.2, headwidth=7.5, headlength=7.5),
        zorder=4
    )

    # ==========================================
    # --- COLUMN 2: SAFETY ISOLATION & GUARDRAILS ---
    # ==========================================
    col2_x = 35.8

    pill2 = patches.FancyBboxPatch(
        (col2_x, col_y + col_h + 1.2), col_w, 3.6,
        boxstyle="round,pad=0.5,rounding_size=1.2",
        facecolor=C_ACCENT_PURPLE,
        edgecolor=C_ACCENT_PURPLE,
        linewidth=1.0,
        zorder=3
    )
    ax.add_patch(pill2)
    ax.text(
        col2_x + col_w / 2, col_y + col_h + 3.0, "2. SAFETY GUARDRAILS & ISOLATION",
        ha="center", va="center",
        fontsize=9.2, fontweight="bold", color="#FFFFFF",
        fontname="DejaVu Sans", zorder=4
    )

    card2 = patches.FancyBboxPatch(
        (col2_x, col_y), col_w, col_h,
        boxstyle="round,pad=0.8,rounding_size=2.0",
        facecolor="#FAF5FF",
        edgecolor=C_ACCENT_PURPLE,
        linewidth=1.8,
        zorder=2
    )
    ax.add_patch(card2)

    ax.text(
        col2_x + col_w / 2, col_y + col_h - 3.8, "Containment & Defense Envelope",
        ha="center", va="center",
        fontsize=12.0, fontweight="bold", color=C_ACCENT_PURPLE,
        fontname="DejaVu Sans", zorder=3
    )

    guardrails = [
        ("Blast Radius Isolation", "Strict Container Scoping", "Chaos scoped strictly to Payments/Checkout\ncontainers; 100% isolation with zero spillover."),
        ("Confidence Policy Gate", "SR-3 & SR-11 Enforcer", "Autonomous repair requires Conf >= 80%.\nAmbiguous cases safely route to Human Gate."),
        ("Dynamic Circuit Breakers", "SR-9 Flapping Prevention", "Trips automatically after 3 consecutive repair\nfailures, preventing infinite flapping loops."),
        ("Instant Safety Abort", "Emergency Stop Switch", "One-click hardware/software emergency switch\ninstantly restoring last known-good snapshot.")
    ]

    gd_y = col_y + col_h - 7.5
    for g_title, g_type, g_desc in guardrails:
        gd_box = patches.FancyBboxPatch(
            (col2_x + 1.2, gd_y - 14.2), col_w - 2.4, 13.8,
            boxstyle="round,pad=0.5,rounding_size=1.2",
            facecolor="#FFFFFF",
            edgecolor="#DDD6FE",
            linewidth=1.2,
            zorder=3
        )
        ax.add_patch(gd_box)

        ax.text(
            col2_x + 2.2, gd_y - 2.8, g_title,
            ha="left", va="center",
            fontsize=9.5, fontweight="bold", color="#581C87",
            fontname="DejaVu Sans", zorder=4
        )
        ax.text(
            col2_x + 2.2, gd_y - 5.5, f"Rule: {g_type}",
            ha="left", va="center",
            fontsize=8.5, fontweight="bold", color=C_ACCENT_PURPLE,
            fontname="DejaVu Sans", zorder=4
        )
        ax.text(
            col2_x + 2.2, gd_y - 9.8, g_desc,
            ha="left", va="center",
            fontsize=8.0, color="#475569",
            fontname="DejaVu Sans", zorder=4
        )
        gd_y -= 15.6

    # Connecting Arrow 2 -> 3
    ax.annotate(
        "", xy=(67.8, 50.5), xytext=(64.8, 50.5),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=2.2, headwidth=7.5, headlength=7.5),
        zorder=4
    )

    # ==========================================
    # --- COLUMN 3: COMPARATIVE EVALUATION HARNESS & METRICS ---
    # ==========================================
    col3_x = 68.0

    pill3 = patches.FancyBboxPatch(
        (col3_x, col_y + col_h + 1.2), col_w, 3.6,
        boxstyle="round,pad=0.5,rounding_size=1.2",
        facecolor=C_ACCENT_TEAL,
        edgecolor=C_ACCENT_TEAL,
        linewidth=1.0,
        zorder=3
    )
    ax.add_patch(pill3)
    ax.text(
        col3_x + col_w / 2, col_y + col_h + 3.0, "3. BENCHMARKING & METRIC HARNESS",
        ha="center", va="center",
        fontsize=9.2, fontweight="bold", color="#FFFFFF",
        fontname="DejaVu Sans", zorder=4
    )

    card3 = patches.FancyBboxPatch(
        (col3_x, col_y), col_w, col_h,
        boxstyle="round,pad=0.8,rounding_size=2.0",
        facecolor="#F0FDF4",
        edgecolor=C_ACCENT_TEAL,
        linewidth=1.8,
        zorder=2
    )
    ax.add_patch(card3)

    ax.text(
        col3_x + col_w / 2, col_y + col_h - 3.8, "Quantitative Evaluation Metrics",
        ha="center", va="center",
        fontsize=12.0, fontweight="bold", color=C_ACCENT_TEAL,
        fontname="DejaVu Sans", zorder=3
    )

    metrics_defs = [
        ("Mean Time to Recovery (MTTR)", "MTTR = T_recovered - T_detected", "Measures downtime: total duration from alarm\ntrigger to confirmed HTTP 200 health probe."),
        ("Detection Latency (MTTD)", "MTTD = T_detected - T_fault_injected", "Measures responsiveness: time delta between fault\ninjection and evidence bundle creation."),
        ("Diagnostic RCA Accuracy", "Accuracy = (Correct RCA / Total) * 100", "Evaluates root-cause correctness compared\nagainst injected ground-truth fault states."),
        ("Conventional SRE Baseline", "Calibrated Manual Runbooks", "Baseline comparison modeled on industry\nstandard SRE manual triage (400-600s).")
    ]

    mt_y = col_y + col_h - 7.5
    for m_title, m_form, m_desc in metrics_defs:
        mt_box = patches.FancyBboxPatch(
            (col3_x + 1.2, mt_y - 14.2), col_w - 2.4, 13.8,
            boxstyle="round,pad=0.5,rounding_size=1.2",
            facecolor="#FFFFFF",
            edgecolor="#A7F3D0",
            linewidth=1.2,
            zorder=3
        )
        ax.add_patch(mt_box)

        ax.text(
            col3_x + 2.2, mt_y - 2.8, m_title,
            ha="left", va="center",
            fontsize=9.5, fontweight="bold", color="#065F46",
            fontname="DejaVu Sans", zorder=4
        )
        ax.text(
            col3_x + 2.2, mt_y - 5.5, f"Formula: {m_form}",
            ha="left", va="center",
            fontsize=8.5, fontweight="bold", color=C_PRIMARY,
            fontname="DejaVu Sans", zorder=4
        )
        ax.text(
            col3_x + 2.2, mt_y - 9.8, m_desc,
            ha="left", va="center",
            fontsize=8.0, color="#475569",
            fontname="DejaVu Sans", zorder=4
        )
        mt_y -= 15.6

    # ==========================================
    # BOTTOM PROTOCOL GUARANTEE BANNER
    # ==========================================
    banner = patches.FancyBboxPatch(
        (3.5, 2.5), 93.0, 8.0,
        boxstyle="round,pad=0.8,rounding_size=1.8",
        facecolor="#1E293B",
        edgecolor="#0F172A",
        linewidth=1.5,
        zorder=3
    )
    ax.add_patch(banner)

    ax.text(
        50.0, 7.8, "EXPERIMENTAL BENCHMARK RIGOR & EVALUATION GUARANTEES",
        ha="center", va="center",
        fontsize=9.8, fontweight="bold", color="#38BDF8",
        fontname="DejaVu Sans", zorder=4
    )
    ax.text(
        50.0, 4.8, "• Empirical Ground Truth Matching  |  • 100% Blast Radius Containment  |  • Cryptographic SHA-256 Chained Event Logging",
        ha="center", va="center",
        fontsize=8.8, color="#E2E8F0",
        fontname="DejaVu Sans", zorder=4
    )

    plt.tight_layout()
    plt.savefig(output_png, bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Chaos Evaluation Protocol diagram successfully saved: {output_png}")

if __name__ == "__main__":
    draw_chaos_protocol_diagram()
