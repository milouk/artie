# Artie

Artie is a powerful art scraper designed for Anbernic devices running MuOS. It helps you download and manage artwork for your ROMs, enhancing your gaming experience with beautiful visuals and a highly optimized, responsive interface.

<div style="display: flex; justify-content: space-between;">
  <img src="screenshots/artie1.png" alt="Artie Screenshot 1" style="width: 48%;"/>
  <img src="screenshots/artie2.png" alt="Artie Screenshot 2" style="width: 48%;"/>
</div>

## Features

- **Easy-to-use and minimal UI** inspired from [tiny-scraper](https://github.com/Julioevm/tiny-scraper)
- **Enhanced UI performance** with atomic transitions and smooth animations
- **Advanced caching system** for improved performance and reduced API calls
- **Comprehensive error handling and logging** with detailed error tracking
- **Enhanced navigation** with page jumping capabilities (R1/R2, L1/L2)
- **Improved input responsiveness** with optimized button handling
- **Clean, production-ready codebase** with maintainable architecture
- Scrape per system or individual ROM
- Integrates seamlessly with MuOS
- Highly customizable through `config.json`
- Support for Box Art, Preview and Text (Synopsis)
- Option to delete all media for a selected system
- Works on other OSs with minimal adaptation
- Supported media includes `["box-2D", "box-3D", "mixrbv1", "mixrbv2", "ss", "marquee"]`

## What's New - Recent Improvements

This enhanced version of Artie includes significant improvements over the original:

### Performance & Stability
- **Fixed view transition flash issues** - Smooth, seamless transitions between screens
- **Advanced caching system** - Intelligent ROM data and media caching for faster loading
- **Enhanced error recovery** - Robust error handling with automatic recovery mechanisms
- **Improved memory management** - Optimized resource usage and cleanup

### User Experience
- **Enhanced B button responsiveness** - Immediate feedback and consistent behavior
- **Page navigation in ROM view** - Quick navigation through large ROM collections
- **Atomic state transitions** - Prevents UI inconsistencies and improves reliability
- **Improved input handling** - More responsive and accurate control input

### Technical Improvements
- **Comprehensive logging system** - Detailed logs for troubleshooting and debugging
- **Code cleanup and refactoring** - Maintainable, well-structured codebase
- **Enhanced architecture** - Modular design with clear separation of concerns
- **Production-ready stability** - Extensive testing and error handling

## Navigation Controls

Artie supports intuitive navigation controls optimized for handheld gaming devices:

### Standard Navigation
- **D-pad**: Navigate through menus and options
- **A button**: Select/confirm actions
- **B button**: Go back/cancel (enhanced responsiveness)

### Advanced Navigation
- **L1/R1 buttons**: Jump by pages in ROM lists for quick navigation
- **L2/R2 buttons**: Large jumps through ROM collections
- **Page navigation**: Consistent across both systems and ROM views

### Quick Actions
- Navigate large ROM collections efficiently with page jumping
- Instant feedback on all button presses
- Consistent behavior across all interface screens

## Installation / Usage

Follow these steps to install Artie:

1. **Download the Latest Release**:

   - Visit the [releases page](https://github.com/milouk/artie/releases) and download the latest version of Artie.

2. **Unzip the Downloaded File**:

   - Extract the contents of the downloaded zip file.

3. **Configure Artie**:

   In `Artie/.artie/config.json` ensure:

   a) `roms` is correctly configured to the path your roms are located.

   b) Add your [Screenscraper](https://screenscraper.fr/) credentials.

   c) For the systems you are interested to scrape ensure the paths are correct.

4. **Copy Files to MuOS**:

   - Copy the `Artie` directory to `/mnt/mmc/MUOS/application/`.

   This could be done via CLI with:

   `scp -r Artie/ root@<your IP>:/mnt/mmc/MUOS/application/`

5. **Launch Artie Scraper**:

   - Open MuOS and launch Artie Scraper from your applications menu.

## Troubleshooting

### Before Reporting Issues

**Always check the log file first**: Before reporting any errors or issues, please check the log file located at:
```
/mnt/mmc/MUOS/application/.artie/log.txt
```

This file contains detailed information about any errors, performance issues, or unexpected behavior that can help diagnose problems quickly.

### Common Issues and Solutions

#### Application Won't Start
- Check that all files are properly copied to `/mnt/mmc/MUOS/application/Artie/`
- Verify that `config.json` is properly formatted
- Check the log file for specific error messages

#### Slow Performance
- The caching system should improve performance after initial use
- Check available storage space on your device
- Review the log file for any caching issues

#### Navigation Issues
- Ensure your device's controls are properly calibrated
- Try restarting the application if navigation becomes unresponsive
- Check for any error messages in the log file

#### Scraping Problems
- Verify your Screenscraper credentials in `config.json`
- Check your internet connection
- Review API rate limiting messages in the log file
- Ensure ROM file paths are correctly configured

#### Media Not Displaying
- Check that media files were successfully downloaded
- Verify file permissions and storage space
- Review the log file for download errors

### Getting Help

If you continue to experience issues after checking the log file and trying the solutions above:

1. Include relevant portions of your `log.txt` file when reporting issues
2. Provide your device model and MuOS version
3. Describe the steps that led to the problem
4. Open an issue on the [GitHub issues page](https://github.com/milouk/artie/issues)

## Technical Details

### Architecture
- **Atomic state transitions**: Ensures UI consistency and prevents race conditions
- **Advanced caching**: Intelligent ROM data and media caching with automatic cleanup
- **Modular design**: Clean separation between UI, data management, and API layers
- **Error recovery**: Comprehensive error handling with graceful degradation

### Performance Features
- **Optimized rendering**: Smooth transitions and responsive UI updates
- **Memory management**: Efficient resource usage and automatic cleanup
- **Caching strategy**: Smart caching of ROM metadata and artwork
- **Input optimization**: Low-latency input handling for responsive controls

### Logging and Debugging
- **Comprehensive logging**: Detailed logs for all operations and errors
- **Performance monitoring**: Tracking of load times and resource usage
- **Error tracking**: Detailed error information for troubleshooting
- **Debug information**: Helpful debugging data for development and support

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

   - Push your changes to your fork and submit a pull request to the main repository. Be sure to mention what feature you are implementing or which bug you are fixing.

### Reporting Bugs

If you encounter any bugs, please:

1. **Check the log file first** at `/mnt/mmc/MUOS/application/.artie/log.txt`
2. Open an issue on the [GitHub issues page](https://github.com/milouk/artie/issues) with:
   - Detailed information about the problem
   - Relevant log file excerpts
   - Steps to reproduce the issue
   - Your device and MuOS version information

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

Thank you for using Artie! This enhanced version provides a significantly improved experience with better performance, reliability, and user experience on your Anbernic device.
