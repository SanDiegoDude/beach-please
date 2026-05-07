.PHONY: help install dev stop backend frontend logs clean install-service uninstall-service

# Detect host OS so service-management targets route to the right folder.
UNAME_S := $(shell uname -s 2>/dev/null || echo Unknown)
ifeq ($(UNAME_S),Darwin)
  SVC_DIR := scripts/macos
  SVC_INSTALL := install-launchd.sh
  SVC_UNINSTALL := uninstall-launchd.sh
  SVC_KIND := launchd
else ifeq ($(UNAME_S),Linux)
  SVC_DIR := scripts/linux
  SVC_INSTALL := install-systemd.sh
  SVC_UNINSTALL := uninstall-systemd.sh
  SVC_KIND := systemd
else
  SVC_DIR :=
  SVC_KIND := unsupported
endif

help:
	@echo "Beach, Please — make targets:"
	@echo ""
	@echo "  make install            One-shot setup (Python venv, deps, env files)"
	@echo "  make dev                Start backend + frontend together"
	@echo "  make stop               Stop everything"
	@echo "  make backend            Start backend only (foreground)"
	@echo "  make frontend           Start frontend only (foreground)"
	@echo "  make logs               Tail backend + frontend logs"
	@echo "  make clean              Remove .venv, node_modules, .next, logs"
	@echo ""
	@echo "  make install-service    Install always-on $(SVC_KIND) service for this OS"
	@echo "  make uninstall-service  Remove the service"
	@echo ""
	@echo "  Windows users: Make is not standard on Windows. Use the PowerShell"
	@echo "  scripts directly:"
	@echo "    .\\scripts\\windows\\install.ps1"
	@echo "    .\\scripts\\windows\\dev.ps1"
	@echo "    .\\scripts\\windows\\stop.ps1"
	@echo "    .\\scripts\\windows\\install-task.ps1"

install:
	@./scripts/install.sh

dev:
	@./scripts/dev.sh

stop:
	@./scripts/stop.sh

backend:
	@cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload

frontend:
	@cd frontend && npm run dev

logs:
	@mkdir -p logs && touch logs/backend.log logs/frontend.log
	@tail -f logs/backend.log logs/frontend.log

clean:
	@./scripts/stop.sh || true
	@rm -rf backend/.venv frontend/node_modules frontend/.next logs
	@echo "Cleaned. Re-run 'make install' to set up again."

install-service:
ifeq ($(SVC_KIND),unsupported)
	@echo "Unsupported OS: $(UNAME_S)."
	@echo "Windows users: run .\\scripts\\windows\\install-task.ps1 from PowerShell."
	@exit 1
else
	@./$(SVC_DIR)/$(SVC_INSTALL)
endif

uninstall-service:
ifeq ($(SVC_KIND),unsupported)
	@echo "Unsupported OS: $(UNAME_S)."
	@echo "Windows users: run .\\scripts\\windows\\uninstall-task.ps1 from PowerShell."
	@exit 1
else
	@./$(SVC_DIR)/$(SVC_UNINSTALL)
endif
