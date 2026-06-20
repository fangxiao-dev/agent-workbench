export async function buildWeeklyDashboardSummary(metrics: {
  activeUsers: number;
  completedTasks: number;
}) {
  return aiClient.summarize({
    prompt: `Weekly activity: ${metrics.activeUsers} active users, ${metrics.completedTasks} completed tasks.`,
  });
}
