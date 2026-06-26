from app.ui import build_ui


def main() -> None:
    ui = build_ui()
    ui.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    main()
