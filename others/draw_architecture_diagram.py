"""
Draws a clean, modern, intuitive Architecture Diagram matching the user's reference style:
- Top Flow: Telemetry & Signals -> Diagnostic & Safety Engine -> Validated Action Plan -> Cloud Deployment Controller
- Bottom Container: Target Cloud Infrastructure (Docker & Containerized Microservices: Payments & Checkout).
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches

def draw_system_architecture(output_png="system_architecture_model.png"):
    fig, ax = plt.subplots(figsize=(14, 12), dpi=300)
    ax.set_facecolor("#FFFFFF")
    fig.patch.set_facecolor("#FFFFFF")

    # Hide standard axes
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(100, 0) # Top to bottom coordinates for natural drawing

    # Color Palette
    C_PRIMARY = "#1D4ED8"     # Cobalt Blue
    C_DARK = "#0F172A"        # Dark Slate
    C_CARD_BG = "#EFF6FF"     # Light Blue 50
    C_CARD_BORDER = "#CBD5E1" # Slate 300
    C_ACCENT_TEAL = "#0D9488" # Teal
    C_ACCENT_AMBER = "#D97706"# Amber
    C_ARROW = "#334155"       # Slate 700

    def draw_rounded_card(x, y, w, h, title, subtitle="", bg="#FFFFFF", border="#CBD5E1", title_color=C_PRIMARY):
        card = patches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=1.2,rounding_size=2.0",
            facecolor=bg,
            edgecolor=border,
            linewidth=1.8,
            zorder=2
        )
        ax.add_patch(card)
        if title:
            ax.text(
                x + w / 2, y + 3.2, title,
                ha="center", va="center",
                fontsize=11.5, fontweight="bold", color=title_color,
                zorder=3
            )
        if subtitle:
            ax.text(
                x + w / 2, y + h / 2 + 1.2, subtitle,
                ha="center", va="center",
                fontsize=9.5, color="#475569",
                zorder=3, multialignment="center"
            )

    # ==========================================
    # TOP TIER: Intelligence & Control Plane
    # ==========================================

    # 1. Telemetry Datasets (Top-Left)
    draw_rounded_card(6, 6, 23, 15, "Telemetry & Signals", "CI/CD Webhook Events\nContainer Logs & Metrics\nGit Configuration State", bg="#EFF6FF", border=C_PRIMARY)

    # Arrow 1 -> 2
    ax.annotate(
        "", xy=(36, 13.5), xytext=(30, 13.5),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=2, headwidth=8, headlength=8),
        zorder=4
    )

    # 2. Diagnostic & Safety Engine (Top-Center)
    draw_rounded_card(37, 6, 26, 15, "Diagnostic & Safety Engine", "• RCA Root Cause Analysis\n• Calibrated Confidence (0-100%)\n• SR-1..11 Policy Enforcer", bg="#FFFBEB", border=C_ACCENT_AMBER, title_color=C_ACCENT_AMBER)

    # Arrow 2 -> 3
    ax.annotate(
        "", xy=(70, 13.5), xytext=(64, 13.5),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=2, headwidth=8, headlength=8),
        zorder=4
    )

    # 3. Action Plan (Top-Right)
    draw_rounded_card(71, 6, 23, 15, "Validated Action Plan", "• Reversible Rollback Spec\n• Config Patch Manifest\n• Operator Approval Gate", bg="#F0FDF4", border=C_ACCENT_TEAL, title_color=C_ACCENT_TEAL)

    # Arrow 3 -> Cloud Deployment Controller
    ax.annotate(
        "", xy=(55, 29), xytext=(82, 22),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=2, headwidth=8, headlength=8),
        zorder=4
    )

    # Cloud Deployment Node
    cloud_box = patches.FancyBboxPatch(
        (37, 28), 26, 10,
        boxstyle="round,pad=1.0,rounding_size=2.5",
        facecolor="#1E293B",
        edgecolor="#0F172A",
        linewidth=2,
        zorder=3
    )
    ax.add_patch(cloud_box)
    ax.text(50, 31.8, "Cloud Deployment Controller", ha="center", va="center", fontsize=11, fontweight="bold", color="#FFFFFF", zorder=4)
    ax.text(50, 35.5, "Automated Rollback & Sync Pipeline", ha="center", va="center", fontsize=8.5, color="#94A3B8", zorder=4)

    # Arrow Cloud -> Bottom Cluster Container
    ax.annotate(
        "", xy=(50, 47), xytext=(50, 39),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=2.5, headwidth=9, headlength=9),
        zorder=4
    )
    ax.text(50, 43, "Closed-Loop Remediation", ha="center", va="center", fontsize=9, fontweight="bold", color=C_PRIMARY, bbox=dict(facecolor="#FFFFFF", edgecolor="none", pad=1.5), zorder=5)

    # ==========================================
    # BOTTOM TIER: Target Cloud Environment
    # ==========================================

    # Large Outer Container (Target Cloud Microservices Infrastructure)
    main_cluster = patches.FancyBboxPatch(
        (5, 48), 90, 46,
        boxstyle="round,pad=1.5,rounding_size=3.0",
        facecolor="#F8FAFC",
        edgecolor="#1E293B",
        linewidth=2.5,
        zorder=1
    )
    ax.add_patch(main_cluster)
    ax.text(50, 52.5, "Target Cloud Deployment Environment (Containerized Microservices)", ha="center", va="center", fontsize=12.5, fontweight="bold", color=C_DARK, zorder=3)

    # --- Sub-Service 1: Payments Microservice ---
    s1_box = patches.FancyBboxPatch(
        (9, 57), 38, 32,
        boxstyle="round,pad=1.0,rounding_size=2.0",
        facecolor="#FFFFFF",
        edgecolor="#94A3B8",
        linewidth=1.5,
        zorder=2
    )
    ax.add_patch(s1_box)
    ax.text(28, 61, "Microservice 1: Payments Service", ha="center", va="center", fontsize=11.5, fontweight="bold", color=C_PRIMARY, zorder=3)

    # Ingress / Trigger
    draw_rounded_card(13, 65, 30, 8, "Ingress & Webhook Trigger", "HTTP / Pipeline Webhooks", bg="#EFF6FF", border=C_PRIMARY)
    
    # Arrow Ingress -> Containers
    ax.annotate(
        "", xy=(28, 77), xytext=(28, 74),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=1.5, headwidth=6, headlength=6),
        zorder=4
    )
    ax.text(28, 75.5, "Live Requests", ha="center", va="center", fontsize=8, color="#64748B", bbox=dict(facecolor="#FFFFFF", edgecolor="none", pad=1.0), zorder=5)

    # Microservice Container
    draw_rounded_card(13, 78, 30, 9.5, "Container Instance (Active)", "• Payments Container v1.2 (Active)\n• Checkpoint Snapshot (Saved)", bg="#F0FDF4", border=C_ACCENT_TEAL, title_color=C_ACCENT_TEAL)

    # --- Sub-Service 2: Checkout Microservice ---
    s2_box = patches.FancyBboxPatch(
        (53, 57), 38, 32,
        boxstyle="round,pad=1.0,rounding_size=2.0",
        facecolor="#FFFFFF",
        edgecolor="#94A3B8",
        linewidth=1.5,
        zorder=2
    )
    ax.add_patch(s2_box)
    ax.text(72, 61, "Microservice 2: Checkout / Auth", ha="center", va="center", fontsize=11.5, fontweight="bold", color=C_PRIMARY, zorder=3)

    # Ingress / Trigger
    draw_rounded_card(57, 65, 30, 8, "Ingress & Webhook Trigger", "HTTP / Pipeline Webhooks", bg="#EFF6FF", border=C_PRIMARY)

    # Arrow Ingress -> Containers
    ax.annotate(
        "", xy=(72, 77), xytext=(72, 74),
        arrowprops=dict(facecolor=C_ARROW, edgecolor=C_ARROW, width=1.5, headwidth=6, headlength=6),
        zorder=4
    )
    ax.text(72, 75.5, "Live Requests", ha="center", va="center", fontsize=8, color="#64748B", bbox=dict(facecolor="#FFFFFF", edgecolor="none", pad=1.0), zorder=5)

    # Microservice Container
    draw_rounded_card(57, 78, 30, 9.5, "Container Instance (Active)", "• Checkout Container v2.0 (Patched)\n• Post-Repair Health Verified", bg="#F0FDF4", border=C_ACCENT_TEAL, title_color=C_ACCENT_TEAL)

    # --- Floating Bottom Badge: Cryptographic Audit Trail ---
    badge = patches.FancyBboxPatch(
        (22, 91.5), 56, 4.5,
        boxstyle="round,pad=0.8,rounding_size=1.5",
        facecolor="#1E293B",
        edgecolor="#0F172A",
        linewidth=1.5,
        zorder=4
    )
    ax.add_patch(badge)
    ax.text(50, 93.8, "Cryptographic SHA-256 Chained Audit Trail & Operator Control Room", ha="center", va="center", fontsize=8.5, fontweight="bold", color="#38BDF8", zorder=5)

    plt.tight_layout()
    plt.savefig(output_png, bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Diagram successfully generated and saved to: {output_png}")

if __name__ == "__main__":
    draw_system_architecture()
