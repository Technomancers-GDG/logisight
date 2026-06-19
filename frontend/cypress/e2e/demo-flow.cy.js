describe("Logisight — Core Demo Flow", () => {
  beforeEach(() => {
    cy.intercept("GET", "/api/dashboard", { fixture: "dashboard.json" }).as("getDashboard");
    cy.intercept("GET", "/api/facilities", []).as("getFacilities");
    cy.intercept("GET", "/api/vehicles", []).as("getVehicles");
    cy.intercept("GET", "/api/drivers", []).as("getDrivers");
    cy.intercept("GET", "/api/objectives", []).as("getObjectives");
    cy.intercept("GET", "/api/routes", []).as("getRoutes");
    cy.intercept("GET", "/api/scenarios", []).as("getScenarios");
    cy.intercept("GET", "/api/recommendations", []).as("getRecommendations");
    cy.intercept("GET", "/api/metrics/sdg", {}).as("getSdg");
    cy.intercept("GET", "/api/events/news?relevant_only=true", []).as("getEvents");
    cy.intercept("GET", "/api/forecast/risk?hours=12", []).as("getRiskForecast");
    cy.intercept("GET", "/api/inventory/forecasts", []).as("getInventoryForecast");
    cy.intercept("GET", "/api/inventory/proactive-dispatches", []).as("getProactiveDispatches");
    cy.intercept("GET", "/api/metrics/ai-activity", []).as("getAiActivity");
    cy.intercept("GET", "/api/rl/stats", { fixture: "rl-stats.json" }).as("getRlStats");
    cy.intercept("GET", "/api/rl/training-history?limit=500", { fixture: "rl-training-history.json" }).as("getRlHistory");
    cy.intercept("GET", "/api/rl/episodes?limit=50", []).as("getRlEpisodes");
    cy.intercept("GET", "/api/rl/action-distribution", { counts: {}, percentages: {}, total: 0, window: 200 }).as("getRlDist");
    cy.intercept("GET", "/api/rl/q-values", null).as("getRlQvalues");

    cy.visit("/");
    cy.wait(["@getDashboard", "@getFacilities", "@getVehicles", "@getObjectives", "@getRoutes"]);
  });

  /* ── 1. App loads and shows the dashboard ── */
  it("loads the dashboard view with core metrics", () => {
    cy.get(".view-dashboard").should("exist");
    cy.contains("Command Center").should("be.visible");
    cy.contains("Supply Chain Digital Twin").should("be.visible");
    cy.get(".sidebar").should("be.visible");
    cy.get(".nav-item.active").should("contain", "Dashboard");
  });

  /* ── 2. Navigation between key views ── */
  it("navigates to Live Map view", () => {
    cy.contains(".nav-item", "Live Map").click();
    cy.get(".map-container").should("exist");
    cy.contains("Route & Facility Map with Risk Heatmap").should("be.visible");
  });

  it("navigates to RL Training view", () => {
    cy.contains(".nav-item", "RL Training").click();
    cy.wait("@getRlStats");
    cy.contains("RL Agent").should("be.visible");
    cy.contains("Learning Curves").should("be.visible");
    cy.contains("Advanced Training Metrics").should("be.visible");
    cy.contains("Q-Value Confidence").should("be.visible");
    cy.contains("Replay Buffer Growth").should("be.visible");
    cy.contains("Training Throughput").should("be.visible");
    cy.contains("Action Distribution").should("be.visible");
    cy.contains("Q-Value Snapshot").should("be.visible");
    cy.contains("Recent Episodes").should("be.visible");
    cy.contains("Training Controls").should("be.visible");
  });

  it("navigates to Risk Forecast view", () => {
    cy.contains(".nav-item", "Risk Forecast").click();
    cy.get(".view-forecast").should("exist");
  });

  it("navigates to Scenarios view", () => {
    cy.contains(".nav-item", "Scenarios").click();
    cy.get(".view-scenarios").should("exist");
  });

  it("navigates to AI Decisions view", () => {
    cy.contains(".nav-item", "AI Decisions").click();
    cy.contains("AI Decision").should("be.visible");
  });

  it("navigates to Settings view", () => {
    cy.contains(".nav-item", "Settings").click();
    cy.get(".view-settings").should("exist");
  });

  /* ── 3. Simulation controls ── */
  it("shows simulation controls in demo mode", () => {
    cy.contains("Start").should("be.visible");
    cy.contains("Reset").should("be.visible");
    cy.get(".speed-select").should("exist");
    cy.contains("Accept AI").should("be.visible");
  });

  it("triggers simulation start", () => {
    cy.intercept("POST", "/api/simulation/start", { status: "ok" }).as("simStart");
    cy.contains(".sim-btn.primary", "Start").click();
    cy.wait("@simStart");
  });

  it("changes simulation speed via dropdown", () => {
    cy.intercept("PUT", "/api/simulation/speed", { status: "ok" }).as("setSpeed");
    cy.get(".speed-select").select("60x");
    cy.wait("@setSpeed");
  });

  /* ── 4. RL Training view has interactive controls ── */
  it("RL Training view shows stats and batch training button", () => {
    cy.contains(".nav-item", "RL Training").click();
    cy.wait("@getRlStats");
    cy.contains("Epsilon").should("be.visible");
    cy.contains("Buffer Size").should("be.visible");
    cy.contains("Train Steps").should("be.visible");
    cy.contains("Avg Reward").should("be.visible");
    cy.contains("Exploration vs Exploitation").should("be.visible");
    cy.contains("Run Batch Training").should("be.visible");
    cy.contains("Reset Agent").should("be.visible");
  });

  it("RL Training view triggers batch training", () => {
    cy.intercept("POST", "/api/rl/train-batch", {
      status: "completed", epochs_completed: 100, final_loss: 0.04, final_epsilon: 0.22,
    }).as("trainBatch");
    cy.contains(".nav-item", "RL Training").click();
    cy.wait("@getRlStats");
    cy.contains(".rl-btn-primary", "Run Batch Training").click();
    cy.wait("@trainBatch");
  });

  it("RL Training view charts render with data", () => {
    cy.contains(".nav-item", "RL Training").click();
    cy.wait("@getRlHistory");
    cy.get(".recharts-responsive-container").should("have.length.at", 4);
  });

  /* ── 5. Scenarios view ── */
  it("triggers a scenario", () => {
    cy.intercept("GET", "/api/scenarios", [
      { id: "port_congestion", name: "Port Congestion", description: "Simulate port delays", scenario_type: "disruption" },
    ]).as("getScenariosList");
    cy.intercept("POST", "/api/scenarios/port_congestion/trigger", { status: "applied" }).as("triggerScenario");
    cy.intercept("POST", "/api/simulation/start", { status: "ok" }).as("simStart");

    cy.contains(".nav-item", "Scenarios").click();
    cy.wait("@getScenariosList");
    cy.contains("Port Congestion").should("be.visible");

    cy.contains(".sim-btn.primary", "Start").click();
    cy.wait("@simStart");

    cy.contains("button", "Run Scenario").click();
    cy.wait("@triggerScenario");
  });
});
