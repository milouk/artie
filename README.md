# Artie

Artie is a simple art scraper designed for Anbernic devices running MuOS. It helps you download and manage artwork for your ROMs, enhancing your gaming experience with beautiful visuals.

## Features

- Easy-to-use interface
- Supports multiple systems
- Integrates seamlessly with MuOS

## Installation

Follow these steps to install Artie:

1. **Download the Latest Release**:

   - Visit the [releases page](https://github.com/milouk/artie/releases) and download the latest version of Artie.

2. **Unzip the Downloaded File**:

   - Extract the contents of the downloaded zip file.

3. **Configure Artie**:

   - Open `config.json` and add your ScreenScraper credentials.
   - *Customize other settings such as ROMs path, art path per system, etc.*

4. **Copy Files to MuOS**:

   - Copy the `.artie` directory and `Artie Scraper.sh` script to `/mnt/mmc/MUOS/application/`.

   This could be done with:

   `scp -r .artie/ Artie\ Scraper.sh root@<your IP>:/mnt/mmc/MUOS/application/`

5. **Launch Artie Scraper**:
   - Open MuOS and launch Artie Scraper from your applications menu.

## Usage

1. **Run Artie Scraper**:

   - Navigate to the applications menu in MuOS and select Artie Scraper.

2. **Scrape Artwork**:

   - Follow the on-screen instructions to scrape artwork for your ROMs.

3. **Enjoy Enhanced Visuals**:
   - View your ROMs with the newly downloaded artwork.

## Contributing

We welcome contributions! Feel free to open issues or submit pull requests (PRs) to help improve Artie.

### How to Contribute

1. **Fork the Repository**:

   - Click the "Fork" button at the top right of the repository page.

2. **Clone Your Fork**:

   - Clone your forked repository to your local machine using `git clone`.

3. **Create a Branch**:

   - Create a new branch for your feature or bug fix.

4. **Make Changes**:

   - Implement your changes and commit them with clear and concise messages.

5. **Submit a Pull Request**:
   - Push your changes to your fork and submit a pull request to the main repository.

### Reporting Bugs

If you encounter any bugs, please open an issue on the [GitHub issues page](https://github.com/milouk/artie/issues) with detailed information about the problem.

## Roadmap

### Upcoming Features

- **Multithreading**: Implement multithreading to improve performance and speed up the scraping process.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

Thank you for using Artie! We hope it enhances your gaming experience on your Anbernic device.
