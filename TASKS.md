# Tasks — AI Personal Finance (v2)

> ✅ Fases 0–7 completadas (22 tareas implementadas)
> A continuación, las tareas de la versión 2:

---

## V2-1: CRUD — Edición y Eliminación

- [ ] **T-900** 🔴 Exponer `update_transaction` como tool del agente
- [ ] **T-901** 🔴 Exponer `delete_transaction` / `delete_transactions_batch` como tools
- [ ] **T-902** 🟡 Actualizar system prompt para edición/borrado (con confirmación)

## V2-2: Recomendaciones Multi-Periodo

- [ ] **T-1000** 🔴 Nuevo tool `analyze_spending_trends(months_back)` — compara gasto por categoría entre meses
- [ ] **T-1001** 🟡 Mejorar `get_recommendations` con datos históricos
- [ ] **T-1002** 🟡 Actualizar system prompt para recomendaciones proactivas

## V2-3: Alertas y Sugerencias en Nuevos Gastos

- [ ] **T-1100** 🔴 Tool `detect_spending_anomaly(category, amount, month)` vs promedios históricos
- [ ] **T-1101** 🟡 Integrar en flujo del agente: alerta automática tras crear gasto
- [ ] **T-1102** 🟡 Actualizar system prompt con reglas de alertas post-creación
