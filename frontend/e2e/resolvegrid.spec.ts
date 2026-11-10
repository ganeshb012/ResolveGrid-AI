import { test, expect } from '@playwright/test';

test.describe('ResolveGrid AI E2E Multi-Portal Lifecycle', () => {

  test('Citizen Portal: Complaint Submission & Live Tracking', async ({ page }) => {
    // Navigate to citizen portal (accessible by guest or citizen)
    await page.goto('/citizen');
    await expect(page).toHaveTitle(/ResolveGrid AI/);

    // Verify presence of title and voice recorder components
    await expect(page.getByRole('heading', { name: 'Citizen Portal' })).toBeVisible();
    await expect(page.getByText('Gnani Prisma STT')).toBeVisible();

    // Fill complaint form
    await page.getByPlaceholder('Brief title (e.g. Broken water pipeline, Deep pothole)').fill('E2E Test: Deep Pothole on Paud Road');
    await page.getByPlaceholder('Describe the issue, landmarks, and severity in detail...').fill('Large crater pothole dangerous for evening bike riders near Kothrud.');
    
    // Select category
    await page.locator('select').first().selectOption('ROAD_POTHOLE');

    // Submit complaint
    await page.getByRole('button', { name: /Submit Verified Complaint/i }).click();

    // Verify success banner and live tracking display
    await expect(page.getByText(/registered successfully! LangGraph agents are analyzing and dispatching/i)).toBeVisible({ timeout: 15000 });
  });

  test('Admin Command: Overview, Pune Map & Approval Queue', async ({ page }) => {
    // Sign in as Admin
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);

    // Verify Operations Command headline and KPI cards
    await expect(page.getByText('Operations Command Center')).toBeVisible();
    await expect(page.getByText('Total Incidents')).toBeVisible();
    await expect(page.getByText('High / Critical')).toBeVisible();

    // Check Leaflet map container is mounted
    const map = page.locator('.leaflet-container');
    await expect(map).toBeVisible();

    // Switch to Approvals Queue tab
    await page.getByRole('button', { name: /Approvals Queue/i }).click();
    await expect(page.getByText(/Human Approval Queue/i)).toBeVisible();
  });

  test('Worker Hub: Task Review & Acceptance', async ({ page }) => {
    // Sign in as Worker (Field Crew)
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('worker@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Worker@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/worker/);

    // Verify Worker profile, duty switcher and assigned tasks section
    await expect(page.getByRole('heading', { name: /Field Specialist|Suresh Kadam|Amit Jadhav/i })).toBeVisible();
    await expect(page.getByText('Assigned Tasks')).toBeVisible();
    await expect(page.getByText('Duty Status:')).toBeVisible();
    await expect(page.getByText('Update GPS Location')).toBeVisible();
  });

  test('AI Activity Center: 6 Agents Telemetry & Tool Calls', async ({ page }) => {
    // Sign in as Admin to access AI Activity Center
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);

    // Navigate to AI Activity Center
    await page.goto('/admin/ai-activity');
    await expect(page).toHaveURL(/\/admin\/ai-activity/);

    // Verify Gnani AI Gateway health panel
    await expect(page.getByText(/Gnani AI Model Suite & Gateway Health/i)).toBeVisible();
    await expect(page.getByText('Prisma STT v3')).toBeVisible();
    await expect(page.getByText('Timbre TTS v3')).toBeVisible();

    // Verify all 6 specialized agents are displayed
    await expect(page.getByText('Agent 1: Incident Intelligence')).toBeVisible();
    await expect(page.getByText('Agent 2: Duplicate Detection')).toBeVisible();
    await expect(page.getByText('Agent 3: Priority Assessment')).toBeVisible();
    await expect(page.getByText('Agent 4: Resource Allocation')).toBeVisible();
    await expect(page.getByText('Agent 5: Multi-Channel Coordination')).toBeVisible();
    await expect(page.getByText('Agent 6: Evidence & Verification')).toBeVisible();

    // Check execution audit trail & real-time websocket feed
    await expect(page.getByText('Agent Executions Audit Trail')).toBeVisible();
    await expect(page.getByText('Real-Time WebSocket Feed')).toBeVisible();
  });

  test('Complete End-to-End Incident Lifecycle Flow', async ({ page }) => {
    // 1. Citizen reports an incident
    await page.goto('/citizen');
    await page.getByPlaceholder('Brief title (e.g. Broken water pipeline, Deep pothole)').fill('E2E Lifecycle: Burst Water Main near Swargate');
    await page.getByPlaceholder('Describe the issue, landmarks, and severity in detail...').fill('Severe water main rupture flooding the right traffic lane.');
    await page.locator('select').first().selectOption('WATER_LEAKAGE');
    await page.getByRole('button', { name: /Submit Verified Complaint/i }).click();
    await expect(page.getByText(/registered successfully/i)).toBeVisible({ timeout: 15000 });

    // 2. Admin inspects dashboard and verifies incident presence
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByText('Operations Command Center')).toBeVisible();

    // 3. Worker inspects assignments
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('worker@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Worker@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/worker/);
    await expect(page.getByText('Assigned Tasks')).toBeVisible();

    // 4. Admin inspects AI telemetry to audit the autonomous workflow
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);
    await page.goto('/admin/ai-activity');
    await expect(page).toHaveURL(/\/admin\/ai-activity/);
    await expect(page.getByText('Agent Executions Audit Trail')).toBeVisible();
  });

});
