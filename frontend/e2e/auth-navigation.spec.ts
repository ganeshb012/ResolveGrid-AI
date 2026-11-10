import { test, expect } from '@playwright/test';

test.describe('Role-Based Frontend Route Guards and Navigation', () => {

  test.beforeEach(async ({ page }) => {
    // Catch-all mock for any unhandled /api/v1/* endpoint to prevent accidental 401 session resets in E2E
    await page.route('**/api/v1/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    // Intercept backend API requests so E2E tests run reliably without network/backend flakiness
    await page.route('**/api/v1/auth/login', async (route) => {
      const postData = route.request().postDataJSON() || {};
      const email = postData.email || '';
      const role = email.includes('admin') ? 'ADMIN' : email.includes('worker') ? 'WORKER' : 'CITIZEN';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: `mock-valid-jwt-${role.toLowerCase()}`,
          token_type: 'bearer',
          user_id: `user-${role.toLowerCase()}-uuid`,
          email: email || `${role.toLowerCase()}@resolvegrid.gov.in`,
          role: role,
          full_name: `${role} Demo User`,
          preferred_language: 'en'
        }),
      });
    });

    await page.route('**/api/v1/auth/me', async (route) => {
      const authHeader = route.request().headers()['authorization'] || '';
      const role = authHeader.includes('admin') ? 'ADMIN' : authHeader.includes('worker') ? 'WORKER' : 'CITIZEN';
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: `user-${role.toLowerCase()}-uuid`,
          email: `${role.toLowerCase()}@resolvegrid.gov.in`,
          role: role,
          full_name: `${role} Demo User`,
          preferred_language: 'en',
          is_active: true,
          created_at: new Date().toISOString()
        }),
      });
    });

    await page.route('**/api/v1/workers/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 'worker-uuid-1',
          user_id: 'user-worker-uuid',
          full_name: 'Worker Demo User',
          email: 'worker@resolvegrid.gov.in',
          department_id: 'dept-1',
          department_name: 'Road Maintenance',
          employee_id: 'EMP-RD-101',
          skills: 'Road repairs',
          current_latitude: 18.5204,
          current_longitude: 73.8567,
          is_on_duty: true,
          availability_status: 'AVAILABLE',
          current_active_tasks: 0,
          created_at: new Date().toISOString()
        }),
      });
    });

    await page.route('**/api/v1/assignments*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/v1/incidents*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/v1/analytics/overview', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          incidents: { total: 0, pending: 0, in_progress: 0, high_priority: 0, resolved: 0, escalated: 0, awaiting_approval: 0 },
          workers: { total_workers: 0, available: 0, busy: 0, on_break: 0, off_duty: 0 },
          departments: [],
          recent_activity_count: 0,
          pending_approvals_count: 0
        }),
      });
    });

    await page.route('**/api/v1/workers', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/v1/approvals*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/v1/agents*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/v1/voice*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ok', provider: 'gnani', available: true }),
      });
    });

    await page.route('**/api/v1/users*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'admin-1',
            email: 'admin@resolvegrid.gov.in',
            full_name: 'Rajesh Patil',
            role: 'ADMIN',
            phone: '+91 98220 11111',
            preferred_language: 'en',
            is_active: true,
            created_at: new Date().toISOString()
          },
          {
            id: 'worker-1',
            email: 'worker@resolvegrid.gov.in',
            full_name: 'Suresh Kadam',
            role: 'WORKER',
            department_name: 'Road Maintenance',
            employee_id: 'EMP-RD-101',
            phone: '+91 98220 22222',
            preferred_language: 'mr',
            is_active: true,
            created_at: new Date().toISOString()
          }
        ]),
      });
    });

    await page.route('**/api/v1/auth/register', async (route) => {
      const postData = route.request().postDataJSON() || {};
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          access_token: 'mock-valid-jwt-citizen-registered',
          token_type: 'bearer',
          user_id: 'new-citizen-uuid',
          email: postData.email || 'newcitizen@resolvegrid.gov.in',
          role: 'CITIZEN',
          full_name: postData.full_name || 'New Citizen',
          preferred_language: postData.preferred_language || 'en'
        }),
      });
    });
  });

  test('Direct root URL (/) immediately opens Citizen Portal without bouncing to /login', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto('/');
    await expect(page).toHaveURL(/^https?:\/\/[^/]+\/$/);
    await expect(page.getByRole('heading', { name: 'Citizen Portal' })).toBeVisible();
    await expect(page).not.toHaveURL(/\/login/);
  });

  test('Guest access to citizen portal and restricted navbar', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.clear();
    });

    await page.goto('/citizen');
    await expect(page).toHaveURL(/\/citizen/);
    await expect(page.getByRole('heading', { name: 'Citizen Portal' })).toBeVisible();

    // In navbar, top portal navigation links are restricted for Guests
    await expect(page.getByRole('link', { name: /Citizen Portal/i })).not.toBeVisible();
    await expect(page.getByRole('link', { name: /Operations Command/i })).not.toBeVisible();
    await expect(page.getByRole('link', { name: /Field Crew Hub/i })).not.toBeVisible();
    await expect(page.getByRole('link', { name: /AI Multi-Agent Center/i })).not.toBeVisible();
  });

  test('Guest redirect from admin and worker portals to /login', async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.clear();
    });

    // Visiting /admin as guest -> redirected to /login
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/login/);

    // Visiting /worker as guest -> redirected to /login
    await page.goto('/worker');
    await expect(page).toHaveURL(/\/login/);

    // Visiting /admin/ai-activity as guest -> redirected to /login
    await page.goto('/admin/ai-activity');
    await expect(page).toHaveURL(/\/login/);
  });

  test('Citizen denied worker and admin routes, redirected to /citizen', async ({ page }) => {
    // Log in as Citizen through Login page
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('citizen@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Citizen@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/citizen/);

    // Visiting /worker should redirect to /citizen
    await page.goto('/worker');
    await expect(page).toHaveURL(/\/citizen/);

    // Visiting /admin should redirect to /citizen
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/citizen/);

    // Visiting /admin/ai-activity should redirect to /citizen
    await page.goto('/admin/ai-activity');
    await expect(page).toHaveURL(/\/citizen/);

    // Navbar should not display worker or admin portals for Citizen
    await expect(page.getByRole('link', { name: /Field Crew Hub/i })).not.toBeVisible();
    await expect(page.getByRole('link', { name: /Operations Command/i })).not.toBeVisible();
  });

  test('Worker denied admin routes, allowed worker portal', async ({ page }) => {
    // Log in as Worker through Login page
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('worker@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Worker@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/worker/);

    // Visiting /admin should redirect to /worker
    await page.goto('/admin');
    await expect(page).toHaveURL(/\/worker/);

    // Visiting /admin/ai-activity should redirect to /worker
    await page.goto('/admin/ai-activity');
    await expect(page).toHaveURL(/\/worker/);

    // Page header displays Field Crew Hub, but NOT Admin portals in navbar
    await expect(page.getByText(/Field Crew Hub/i).first()).toBeVisible();
    await expect(page.getByRole('link', { name: /AI Multi-Agent Center/i })).not.toBeVisible();
  });

  test('Admin allowed all portals with full navbar links', async ({ page }) => {
    // Log in as Admin through Login page
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByText(/Operations Command Center/i)).toBeVisible();

    // Admin can visit all routes
    await page.getByRole('link', { name: /AI Multi-Agent Center/i }).click();
    await expect(page).toHaveURL(/\/admin\/ai-activity/);

    await page.goto('/worker');
    await expect(page).toHaveURL(/\/worker/);

    await page.goto('/citizen');
    await expect(page).toHaveURL(/\/citizen/);

    // Navbar shows Admin AI Center link
    await expect(page.getByRole('link', { name: /AI Multi-Agent Center/i })).toBeVisible();
  });

  test('Logout removes authenticated session and redirects to /login', async ({ page }) => {
    // Log in as Admin first
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);

    // Open User Profile dropdown from Navbar
    await page.getByRole('button', { name: /user profile menu/i }).click();

    // Verify "My Profile" option is present
    await expect(page.getByRole('button', { name: /My Profile/i })).toBeVisible();

    // Click logout
    await page.getByRole('button', { name: /Sign Out|Logout/i }).click();

    // URL should redirect to /login
    await expect(page).toHaveURL(/\/login/);

    // Verify localStorage cleared
    const token = await page.evaluate(() => localStorage.getItem('token'));
    const user = await page.evaluate(() => localStorage.getItem('user'));
    expect(token).toBeNull();
    expect(user).toBeNull();
  });

  test('Authentic login, role redirection, and logout for all three roles', async ({ page }) => {
    // 1. Citizen Authentication & Redirection
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('citizen@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Citizen@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/citizen/);
    await expect(page.getByRole('heading', { name: 'Citizen Portal' })).toBeVisible();

    // Logout as Citizen
    await page.getByRole('button', { name: /user profile menu/i }).click();
    await page.getByRole('button', { name: /Sign Out|Logout/i }).click();
    await expect(page).toHaveURL(/\/login/);

    // 2. Worker Authentication & Redirection
    await page.getByPlaceholder(/name@example.com/i).fill('worker@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Worker@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/worker/);
    await expect(page.getByText(/Field Crew Hub/i).first()).toBeVisible();

    // Logout as Worker
    await page.getByRole('button', { name: /user profile menu/i }).click();
    await page.getByRole('button', { name: /Sign Out|Logout/i }).click();
    await expect(page).toHaveURL(/\/login/);

    // 3. Admin Authentication & Redirection
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.getByText(/Operations Command Center/i)).toBeVisible();
    await expect(page.getByRole('link', { name: /AI Multi-Agent Center/i })).toBeVisible();

    // Logout as Admin
    await page.getByRole('button', { name: /user profile menu/i }).click();
    await page.getByRole('button', { name: /Sign Out|Logout/i }).click();
    await expect(page).toHaveURL(/\/login/);
  });

  test('Citizen self-registration and Admin user management portal tab', async ({ page }) => {
    // 1. Citizen self-registration flow
    await page.goto('/register');
    await expect(page.getByRole('heading', { name: 'Citizen Registration' })).toBeVisible();
    await page.getByPlaceholder('Aarav Deshmukh').fill('Aditi Kulkarni');
    await page.getByPlaceholder('citizen@example.com').fill('aditi@example.com');
    await page.getByPlaceholder('+91 98220 00000').fill('+91 98223 34455');
    await page.getByPlaceholder('Min 6 chars').fill('Secret@123');
    await page.getByPlaceholder('Re-enter password').fill('Secret@123');
    await page.getByRole('button', { name: /Complete Citizen Registration/i }).click();

    // After citizen registration -> redirected to /citizen
    await expect(page).toHaveURL(/\/citizen/);
    await expect(page.getByRole('heading', { name: 'Citizen Portal' })).toBeVisible();

    // 2. Admin manages users
    await page.goto('/login');
    await page.getByPlaceholder(/name@example.com/i).fill('admin@resolvegrid.gov.in');
    await page.getByPlaceholder(/••••••••/i).fill('Admin@12345');
    await page.getByRole('button', { name: /Sign In/i }).click();
    await expect(page).toHaveURL(/\/admin/);

    // Click "Manage Users" tab
    await page.getByRole('button', { name: /Manage Users/i }).click();
    await expect(page.getByText('Platform User Management & Access Control')).toBeVisible();
    await expect(page.getByRole('button', { name: /Provision User \/ Field Crew/i })).toBeVisible();

    // Open creation modal
    await page.getByRole('button', { name: /Provision User \/ Field Crew/i }).click();
    await expect(page.getByText(/Provision Field Crew Account|Provision User Account/i)).toBeVisible();
  });

});
