# Lightweight VPN Using Raw Sockets

## 📌 Project Overview

This project is a **lightweight, cross-platform VPN** built using **raw sockets**. It enables **secure, encrypted communication** between two endpoints without relying on traditional VPN protocols. The final product will be a **single executable** for both Windows and Linux.

## 🔥 Features

- **End-to-End Encryption** using AES-256
- **Raw Socket Communication** for direct packet handling
- **Cross-Platform Support** (Windows & Linux)
- **Minimal Setup** – Just run the executable
- **Secure Key Management** (Manual Key Sharing)

## 🚀 How It Works

1. **Sender (Client Mode)**: Captures network packets, encrypts them, and forwards them through a secure tunnel.
2. **Receiver (Server Mode)**: Decrypts received packets and routes them to the intended destination.
3. **Encryption**: Uses **AES-256** for confidentiality.

## 🛠️ Installation & Setup

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/yourusername/lightweight-vpn-raw-sockets.git
cd lightweight-vpn-raw-sockets
```

### 2️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

### 3️⃣ Run the VPN

- **Start the VPN Server** (Receiver):
  ```bash
  python vpn.py --mode receive
  ```
- **Start the VPN Client** (Sender):
  ```bash
  python vpn.py --mode send --dest <receiver_ip>
  ```

## 🔒 Security & Encryption

- Uses **AES-256 encryption** for packet security.
- Manual key sharing for extra security.
- Optional Flask web interface for monitoring.

## 📂 Folder Structure

```
lightweight-vpn-raw-sockets/
│── vpn.py               # Main VPN script
│── encryption.py        # Handles AES encryption
│── key.txt              # Manually shared encryption key
│── web_interface/       # Flask-based monitoring UI
│── README.md            # Project documentation
│── requirements.txt     # Dependencies
```

## 💡 Future Enhancements

- **Add Authentication** to prevent unauthorized access
- **Improve Logging** for monitoring traffic & debugging
- **Web UI Dashboard** to display live traffic statistics

## 📜 License

This project is licensed under the **MIT License**.

---

🚀 **Contributions Welcome!** Feel free to open a pull request if you have suggestions or improvements.