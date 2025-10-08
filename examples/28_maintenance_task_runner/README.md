# Maintenance Task Runner

Run scheduled maintenance tasks using OpenHands SDK via GitHub Actions.

## Usage

### Local Testing

```bash
export LLM_API_KEY="your-api-key"
python run.py maintenance_example.txt
```

### GitHub Actions

1. Go to Actions → "Scheduled Maintenance Task"
2. Click "Run workflow"
3. Enter prompt location (URL or file path)
4. Click "Run workflow"

To enable scheduled runs, uncomment the `schedule` section in `.github/workflows/maintenance-task.yml`.
