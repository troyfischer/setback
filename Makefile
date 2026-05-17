.PHONY: dev dev-stop lint format

dev:
	@echo "Starting Python backend stack..."
	@$(MAKE) -C python dev-rebuild
	@echo "Starting Vite client on http://localhost:8081 ..."
	@cd client && npm run dev

dev-stop:
	@echo "Stopping Python backend stack..."
	@$(MAKE) -C python dev-down

lint:
	@$(MAKE) -C python lint typecheck
	@cd client && npm run typecheck

format:
	@$(MAKE) -C python format
	@cd client && npm run format
