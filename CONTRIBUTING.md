# Contributing to GOES Satellite Dashboard

First off, thank you for considering contributing! 🛰️

This project is built by the satellite hobbyist community, for the community. Every contribution helps make ground station monitoring better for everyone.

## How Can I Contribute?

### 🐛 Reporting Bugs

Found something broken? Please open an issue with:

1. **Description**: What went wrong?
2. **Steps to Reproduce**: How can we see the bug?
3. **Expected Behavior**: What should happen?
4. **Environment**: 
   - Raspberry Pi model
   - OS version (`cat /etc/os-release`)
   - Python version (`python3 --version`)
   - goestools version
5. **Logs**: Output from `journalctl -u goes-dashboard -n 100`

### 💡 Feature Requests

Have an idea? Open an issue describing:

1. **The Problem**: What limitation are you hitting?
2. **Proposed Solution**: How would you solve it?
3. **Alternatives**: Any other approaches you considered?

### 🔧 Pull Requests

Ready to code? Here's how:

1. **Fork** the repository
2. **Clone** your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/goes-dashboard.git
   cd goes-dashboard
   ```
3. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```
4. **Make your changes**
5. **Test locally**:
   ```bash
   cd src
   python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8080
   ```
6. **Commit** with a clear message:
   ```bash
   git commit -m "Add: Description of what you added"
   ```
7. **Push** and open a PR:
   ```bash
   git push origin feature/your-feature-name
   ```

## Code Style

### Python (Backend)

- Follow PEP 8
- Use type hints where practical
- Keep functions focused and documented
- Handle errors gracefully

```python
def get_signal_quality(vit_avg: int) -> str:
    """Determine signal quality from viterbi average.
    
    Args:
        vit_avg: The viterbi error average (lower is better)
        
    Returns:
        Quality string: 'excellent', 'good', 'fair', or 'poor'
    """
    if vit_avg < 300:
        return "excellent"
    # ...
```

### JavaScript/React (Frontend)

- Use functional components with hooks
- Keep components small and focused
- Use Tailwind for styling
- Comment complex logic

## Project Structure

```
goes-dashboard/
├── src/
│   ├── main.py          # FastAPI backend
│   └── static/
│       └── index.html   # React frontend (single file)
├── config.example.json  # Example configuration
├── install.sh           # Installation script
├── README.md
├── LICENSE
└── CONTRIBUTING.md
```

## Testing Checklist

Before submitting a PR, please verify:

- [ ] Dashboard loads without errors
- [ ] Signal stats update correctly
- [ ] Service status shows accurate info
- [ ] Images load and lightbox works
- [ ] Logs viewer works for all services
- [ ] Mobile view is usable
- [ ] No console errors in browser
- [ ] Works on Raspberry Pi (if possible)

## Ideas for Contributions

Looking for something to work on? Here are some ideas:

### Easy
- [ ] Add more color themes
- [ ] Improve mobile responsiveness
- [ ] Add favicon
- [ ] Better error messages

### Medium
- [ ] Historical signal graphs (using Chart.js)
- [ ] Email/Discord alerts for signal loss
- [ ] Multi-language support
- [ ] Dark/light theme toggle

### Advanced
- [ ] WebSocket for real-time updates
- [ ] Multi-receiver support
- [ ] Integration with satdump
- [ ] Prometheus metrics endpoint

## Questions?

- Open an issue for questions
- Join the satellite community Discord/forums
- Check existing issues for similar questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thanks for helping make this project better! 🛰️📡
