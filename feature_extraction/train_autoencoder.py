import datetime
from configs.config import Configuration
from tools.console import Console
from pathlib import Path
from torchvision import transforms
from torch.utils.data import DataLoader
from dataset.uvp_dataset import UvpDataset
from models.classifier_cnn import count_parameters
from models.autoencoder import ConvAutoencoder, ResNetCustom
import torch
import torch.nn as nn
import torch.optim as optim
from tools.utils import plot_loss, memory_usage
from models.loss import FocalLoss, WeightedCrossEntropyLoss
from tools.augmentation import GaussianNoise
from torchvision.transforms import RandomHorizontalFlip, RandomRotation, RandomAffine


def train_autoencoder(config_path, input_path, output_path):

    config = Configuration(config_path, input_path, output_path)

    # Create output directory
    input_folder = Path(input_path)
    output_folder = Path(output_path)

    console = Console(output_folder)
    console.info("Training started ...")

    sampled_images_csv_filename = "sampled_images.csv"
    input_csv = input_folder / sampled_images_csv_filename

    if not input_csv.is_file():
        console.error("The input csv file", input_csv, "does not exist.")
        console.quit("Input csv file does not exist.")

    time_str = str(datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
    rel_training_path = Path("autoencoder_training" + time_str)
    training_path = output_folder / rel_training_path
    config.training_path = training_path
    if not training_path.exists():
        training_path.mkdir(exist_ok=True, parents=True)
    elif training_path.exists():
        console.error("The output folder", training_path, "exists.")
        console.quit("Folder exists, not overwriting previous results.")

    # Save configuration file
    output_config_filename = training_path / "config.yaml"
    config.write(output_config_filename)

    # Define data transformations
    transform = transforms.Compose([
        transforms.Resize((config.sampling.target_size[0], config.sampling.target_size[1])),
        transforms.ToTensor(),
    ])

    # Define data transformations
    transform = transforms.Compose([
        transforms.Resize((config.sampling.target_size[0], config.sampling.target_size[1])),
        RandomHorizontalFlip(),
        RandomRotation(degrees=15),
        RandomAffine(degrees=15, translate=(0.1, 0.1), scale=(0.8, 1.2), shear=15),
        GaussianNoise(std=0.1),
        transforms.ToTensor(),
    ])

    # Create uvp dataset datasets for training and validation
    train_dataset = UvpDataset(root_dir=input_folder,
                               num_class=config.sampling.num_class,
                               csv_file=input_csv,
                               transform=transform,
                               phase='train')

    class_counts = train_dataset.data_frame['label'].value_counts().sort_index().tolist()
    total_samples = sum(class_counts)
    class_weights = [total_samples / (config.sampling.num_class * count) for count in class_counts]
    class_weights_tensor = torch.FloatTensor(class_weights)
    class_weights_tensor = class_weights_tensor / class_weights_tensor.sum()

    # Create data loaders
    train_loader = DataLoader(train_dataset,
                              batch_size=config.autoencoder.batch_size,
                              shuffle=True)

    device = torch.device(f'cuda:{config.base.gpu_index}' if
                          torch.cuda.is_available() and config.base.cpu is False else 'cpu')
    console.info(f"Running on:  {device}")

    if config.autoencoder.architecture_type == 'conv_autoencoder':
        model = ConvAutoencoder(latent_dim=config.autoencoder.latent_dim,
                                input_size=config.sampling.target_size,
                                gray=config.autoencoder.gray)

    elif config.autoencoder.architecture_type == 'resnet18':
        model = ResNetCustom(num_classes=config.sampling.num_class,
                             latent_dim=config.autoencoder.latent_dim,
                             gray=config.autoencoder.gray)

    else:
        console.quit("Please select correct parameter for architecture_type")

    # Loss criterion and optimizer
    if config.autoencoder.loss == 'cross_entropy':
        criterion = nn.CrossEntropyLoss()
    elif config.autoencoder.loss == 'cross_entropy_weight':
        class_weights_tensor = class_weights_tensor.to(device)
        criterion = WeightedCrossEntropyLoss(weight=class_weights_tensor)
    elif config.autoencoder.loss == 'focal':
        criterion = FocalLoss(alpha=1, gamma=2)
    elif config.autoencoder.loss == 'mse':
        criterion = nn.MSELoss()

    # Calculate the number of parameters in millions
    num_params = count_parameters(model) / 1_000_000
    console.info(f"The model has approximately {num_params:.2f} million parameters.")

    model.to(device)

    # test memory usage
    console.info(memory_usage(config, model, device))

    # Loss criterion and optimizer
    optimizer = optim.Adam(model.parameters(), lr=config.autoencoder.learning_rate)

    loss_values = []

    # Training loop
    for epoch in range(config.autoencoder.num_epoch):
        model.train()
        running_loss = 0.0

        for images, labels, _ in train_loader:
            images, labels = images.to(device), labels.to(device)

            if config.autoencoder.architecture_type == 'conv_autoencoder':
                labels = images

            optimizer.zero_grad()
            outputs, _ = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        average_loss = running_loss / len(train_loader)
        loss_values.append(average_loss)
        console.info(f"Epoch [{epoch + 1}/{config.autoencoder.num_epoch}] - Loss: {average_loss:.4f}")
        plot_loss(loss_values, num_epoch=epoch + 1, training_path=config.training_path)

        # save intermediate weight
        if (epoch + 1) % config.autoencoder.save_model_every_n_epoch == 0:
            # Save the model weights
            saved_weights = f'model_weights_epoch_{epoch + 1}.pth'
            saved_weights_file = training_path / saved_weights

            console.info(f"Model weights saved to {saved_weights_file}")
            torch.save(model.state_dict(), saved_weights_file)

    # Create a plot of the loss values
    plot_loss(loss_values, num_epoch=config.autoencoder.num_epoch, training_path=config.training_path)

    # Save the model's state dictionary to a file
    saved_weights = "model_weights_final.pth"
    saved_weights_file = training_path / saved_weights

    torch.save(model.state_dict(), saved_weights_file)

    console.info(f"Final model weights saved to {saved_weights_file}")





