document.addEventListener("DOMContentLoaded", () => {
    const links = document.querySelectorAll(".nav-link");
    const currentPath = window.location.pathname;

    links.forEach((link) => {
        if (link.getAttribute("href") === currentPath) {
            link.classList.add("active");
        }
    });

    const counters = document.querySelectorAll(".counter");
    if (counters.length) {
        const animateCounter = (counter) => {
            const target = Number(counter.dataset.counter || 0);
            const duration = 1300;
            const start = performance.now();

            const tick = (now) => {
                const progress = Math.min((now - start) / duration, 1);
                counter.textContent = Math.floor(progress * target).toString();
                if (progress < 1) {
                    requestAnimationFrame(tick);
                }
            };

            requestAnimationFrame(tick);
        };

        const observer = new IntersectionObserver(
            (entries, obs) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    animateCounter(entry.target);
                    obs.unobserve(entry.target);
                });
            },
            { threshold: 0.4 }
        );

        counters.forEach((counter) => observer.observe(counter));
    }

    const sidebarToggle = document.getElementById("sidebarToggle");
    const sidebar = document.getElementById("dashboardSidebar");
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener("click", () => {
            const wrapper = sidebar.closest(".dashboard-wrapper");
            const collapsed = sidebar.classList.toggle("collapsed");
            if (wrapper) {
                wrapper.classList.toggle("sidebar-collapsed", collapsed);
            }
            sidebarToggle.setAttribute("aria-expanded", String(!collapsed));
        });
    }

    const tour = document.getElementById("onboardingTour");
    if (tour) {
        const steps = Array.from(tour.querySelectorAll(".tour-step"));
        const nextBtn = document.getElementById("tourNext");
        const backBtn = document.getElementById("tourBack");
        const progressText = document.getElementById("tourProgressText");
        const dots = Array.from(document.querySelectorAll("#tourDots .dot"));
        let current = 0;

        const render = () => {
            steps.forEach((step, idx) => {
                step.classList.toggle("active", idx === current);
            });
            dots.forEach((dot, idx) => {
                dot.classList.toggle("active", idx <= current);
            });
            progressText.textContent = `Step ${current + 1} of ${steps.length}`;
            backBtn.disabled = current === 0;
            nextBtn.textContent = current === steps.length - 1 ? "Finish" : "Next";
        };

        nextBtn?.addEventListener("click", () => {
            if (current < steps.length - 1) {
                current += 1;
                render();
            }
        });

        backBtn?.addEventListener("click", () => {
            if (current > 0) {
                current -= 1;
                render();
            }
        });

        render();
    }

    const backlogCount = parseInt(document.getElementById("backlog-count-data")?.dataset?.count || "0", 10);
    if (backlogCount > 0) {
        setTimeout(() => {
            showBacklogToast(backlogCount);
        }, 2000);
    }
});

window.escapeHtml = window.escapeHtml || function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
};

window.showToast = window.showToast || function showToast(message, type) {
    const klass = type === "error" ? "danger" : (type || "info");
    let container = document.getElementById("global-toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "global-toast-container";
        container.className = "toast-container position-fixed top-0 end-0 p-3";
        container.style.zIndex = "3000";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast align-items-center text-bg-${klass} border-0`;
    toast.innerHTML = `<div class="d-flex"><div class="toast-body">${window.escapeHtml(message)}</div><button type="button" class="btn-close btn-close-white m-auto me-2" data-bs-dismiss="toast"></button></div>`;
    container.appendChild(toast);
    if (window.bootstrap && bootstrap.Toast) {
        const bsToast = new bootstrap.Toast(toast, { delay: 2500 });
        bsToast.show();
        toast.addEventListener("hidden.bs.toast", () => toast.remove());
    } else {
        setTimeout(() => toast.remove(), 2500);
    }
};

window.showBacklogToast = function showBacklogToast(count) {
    const toast = document.createElement("div");
    toast.style.cssText = "position:fixed;bottom:100px;right:24px;background:#0B3C5D;color:white;padding:12px 16px;border-radius:8px;z-index:9999;box-shadow:0 4px 20px rgba(0,0,0,0.2);cursor:pointer;max-width:260px;border-left:4px solid #F59E0B;transition:all 0.3s;opacity:0;transform:translateY(10px);";
    toast.innerHTML = `
        <div style="display:flex;gap:10px;align-items:center;">
            <i class="fa fa-list-check" style="color:#F59E0B;font-size:16px;"></i>
            <div>
                <div style="font-size:13px;font-weight:700;">${count} task${count > 1 ? "s" : ""} in Backlog</div>
                <div style="font-size:11px;color:rgba(255,255,255,0.7);margin-top:2px;">Click to view pending tasks</div>
            </div>
            <i class="fa fa-times" style="margin-left:auto;color:rgba(255,255,255,0.5);cursor:pointer;font-size:12px;"></i>
        </div>`;
    toast.onclick = () => {
        window.location.href = "/dashboard/tasks";
    };
    toast.querySelector(".fa-times")?.addEventListener("click", (event) => {
        event.stopPropagation();
        toast.remove();
    });
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "1";
        toast.style.transform = "translateY(0)";
    }, 100);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 300);
    }, 6000);
};

window.confirmDelete = async function confirmDelete(type, id) {
    if (!id) return;
    const names = { dpr: "DPR Report", boq: "BOQ", inventory: "inventory item", task: "task" };
    const confirmed = window.confirm(`Are you sure you want to delete this ${names[type] || "item"}? This cannot be undone.`);
    if (!confirmed) return;

    const urls = {
        dpr: `/dashboard/dpr/${id}/delete`,
        boq: `/dashboard/boq/${id}/delete`,
        inventory: `/dashboard/inventory/delete/${id}`,
        task: `/dashboard/tasks/delete/${id}`,
    };

    try {
        const response = await fetch(urls[type], {
            method: "POST",
            headers: { "Content-Type": "application/json" },
        });
        const data = await response.json();
        if (!data.success) {
            window.showToast(data.error || "Delete failed", "error");
            return;
        }
        window.showToast(`${names[type] || "Item"} deleted`, "success");
        const targets = [
            ...document.querySelectorAll(`[data-id="${id}"]`),
            ...document.querySelectorAll(`[data-task-id="${id}"]`),
        ];
        if (targets.length) {
            targets.forEach((el) => {
                el.style.transition = "all 0.3s";
                el.style.opacity = "0";
                setTimeout(() => el.remove(), 300);
            });
            if (type === "task" && typeof window.updateColumnCounts === "function") {
                setTimeout(() => window.updateColumnCounts(), 320);
            }
        } else {
            setTimeout(() => window.location.reload(), 500);
        }
    } catch (_err) {
        window.showToast("Network error", "error");
    }
};

window.selectedProjectColor = window.selectedProjectColor || "#0B3C5D";

window.openAddProjectModal = function openAddProjectModal(feature) {
    const modalEl = document.getElementById("addProjectModal");
    if (!modalEl) {
        console.warn("addProjectModal not found");
        return;
    }
    const featureInput = document.getElementById("feature-type");
    if (featureInput) featureInput.value = feature || "";

    const openDropdown = document.querySelector(".dropdown-menu.show");
    if (openDropdown) {
        openDropdown.classList.remove("show");
    }

    const modal = new bootstrap.Modal(modalEl);
    modal.show();
};

window.saveNewProject = async function saveNewProject() {
    const nameInput = document.getElementById("new-project-name");
    const name = nameInput ? nameInput.value.trim() : "";
    if (!name) {
        window.showToast("Please enter a project name", "error");
        return;
    }

    const color = document.getElementById("new-project-color")?.value || "#0B3C5D";
    const feature = document.getElementById("feature-type")?.value || "";
    if (!feature) {
        window.showToast("Feature type is required", "error");
        return;
    }
    const btn = document.querySelector('[onclick="saveNewProject()"]');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Saving...';
    }

    try {
        const response = await fetch("/api/feature-projects/add", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, color: color, feature: feature }),
        });
        const data = await response.json();
        if (data.success) {
            const modalEl = document.getElementById("addProjectModal");
            bootstrap.Modal.getInstance(modalEl)?.hide();
            window.showToast(`Project "${name}" added!`, "success");
            setTimeout(() => window.location.reload(), 800);
        } else {
            window.showToast(data.error || "Failed to add project", "error");
        }
    } catch (_err) {
        window.showToast("Network error. Try again.", "error");
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fa fa-save me-2"></i>Save Project';
        }
    }
};

window.deleteFeatureProject = async function deleteFeatureProject(id, name) {
    if (!window.confirm(`Remove "${name}" from this feature?\nRecords stay but project tag is removed.`)) return;
    try {
        const response = await fetch(`/api/feature-projects/delete/${id}`, { method: "POST" });
        const data = await response.json();
        if (!data.success) {
            window.showToast(data.error || "Failed to remove project", "error");
            return;
        }
        window.showToast("Project removed", "success");
        setTimeout(() => window.location.reload(), 600);
    } catch (_err) {
        window.showToast("Network error. Try again.", "error");
    }
};

window.selectProjectColor = function selectProjectColor(color, el) {
    window.selectedProjectColor = color;
    const input = document.getElementById("new-project-color");
    if (input) input.value = color;

    document.querySelectorAll("#addProjectModal .color-swatch").forEach((d) => {
        d.classList.remove("is-selected");
    });

    if (el) {
        el.classList.add("is-selected");
    }
};

/* ── Notification bell shake ─────────────────────────────────────────────
   Adds .has-new to the bell button if unread badge is present, briefly
   animates, then removes the class once the animation ends.            */
(function () {
    document.addEventListener("DOMContentLoaded", function () {
        var bellBtn = document.querySelector('button[aria-label="Notifications"]');
        if (!bellBtn) return;
        bellBtn.classList.add("notification-bell");
        var badge = bellBtn.querySelector(".global-notif-badge");
        if (badge && parseInt(badge.textContent, 10) > 0) {
            bellBtn.classList.add("has-new");
            bellBtn.addEventListener("animationend", function () {
                bellBtn.classList.remove("has-new");
            }, { once: true });
        }
    });
})();
