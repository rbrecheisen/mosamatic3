import torch
import torch.nn as nn
from torch.nn import functional as F


def double_conv(in_c, out_c, dropout_rate):
    conv = nn.Sequential(
        nn.Conv2d(in_c, out_c, kernel_size=3, padding="same"),
        nn.PReLU(),
        nn.BatchNorm2d(out_c),
        nn.Dropout(dropout_rate),
        nn.Conv2d(out_c, out_c, kernel_size=3, padding="same"),
        nn.PReLU(),
        nn.BatchNorm2d(out_c),
    )
    return conv


class UNet(nn.Module):
    def __init__(self, params, num_classes):
        super(UNet, self).__init__()
        # num_classes = params.dict['num_classes_bc']
        dropout_rate = params.dict["dropout_rate"]

        self.max_pool_2x2 = nn.MaxPool2d(kernel_size=2, stride=2)
        self.down_conv_1 = double_conv(1, 32, dropout_rate)
        self.down_conv_2 = double_conv(32, 64, dropout_rate)
        self.down_conv_3 = double_conv(64, 128, dropout_rate)
        self.down_conv_4 = double_conv(128, 256, dropout_rate)
        self.down_conv_5 = double_conv(256, 512, dropout_rate)

        self.up_trans_1 = nn.ConvTranspose2d(
            in_channels=512, out_channels=256, kernel_size=2, stride=2
        )

        self.up_conv_1 = double_conv(512, 256, dropout_rate)

        self.up_trans_2 = nn.ConvTranspose2d(
            in_channels=256, out_channels=128, kernel_size=2, stride=2
        )

        self.up_conv_2 = double_conv(256, 128, dropout_rate)

        self.up_trans_3 = nn.ConvTranspose2d(
            in_channels=128, out_channels=64, kernel_size=2, stride=2
        )

        self.up_conv_3 = double_conv(128, 64, dropout_rate)

        self.up_trans_4 = nn.ConvTranspose2d(
            in_channels=64, out_channels=32, kernel_size=2, stride=2
        )

        self.up_conv_4 = double_conv(64, 32, dropout_rate)

        self.out = nn.Conv2d(in_channels=32, out_channels=num_classes, kernel_size=1)

    def forward(self, image):

        x1 = self.down_conv_1(image)
        # after each convolution apply max_pooling
        p1 = self.max_pool_2x2(x1)

        x2 = self.down_conv_2(p1)
        p2 = self.max_pool_2x2(x2)

        x3 = self.down_conv_3(p2)
        p3 = self.max_pool_2x2(x3)

        x4 = self.down_conv_4(p3)
        p4 = self.max_pool_2x2(x4)

        x5 = self.down_conv_5(p4)

        # decoder
        u6 = self.up_trans_1(x5)
        x6 = self.up_conv_1(torch.cat([u6, x4], 1))

        u7 = self.up_trans_2(x6)
        x7 = self.up_conv_2(torch.cat([u7, x3], 1))

        u8 = self.up_trans_3(x7)
        x8 = self.up_conv_3(torch.cat([u8, x2], 1))

        u9 = self.up_trans_4(x8)
        x9 = self.up_conv_4(torch.cat([u9, x1], 1))

        x = self.out(x9)
        x = F.softmax(x, dim=1)
        return x


class BasicConv2d(nn.Module):
    def __init__(self, in_channels, out_channels, dropout, **kwargs):
        super(BasicConv2d, self).__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size=3,
            stride=1,
            padding="same",
            bias=True,
            **kwargs
        )
        # self.norm = nn.GroupNorm(32, out_channels, affine=True)
        # self.norm = nn.InstanceNorm2d(out_channels, affine=True)
        self.norm = nn.BatchNorm2d(out_channels)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        x = self.conv(x)
        x = self.norm(x)
        x = F.relu(x, inplace=True)
        x = self.dropout(x)
        return x


class AttentionGate2D(nn.Module):
    def __init__(self, in_channels_g, in_channels_l, out_channels, **kwargs):
        super(AttentionGate2D, self).__init__()
        self.wg = nn.Conv2d(
            in_channels_g, out_channels, bias=True, padding=0, kernel_size=1, stride=1
        )
        # self.norm_wg = nn.GroupNorm(num_groups=32, num_channels=out_channels, affine=True)
        # self.norm_wg = nn.InstanceNorm2d(out_channels, affine=True)
        self.norm_wg = nn.BatchNorm2d(out_channels)
        self.wx = nn.Conv2d(
            in_channels_l, out_channels, bias=True, padding=0, kernel_size=1, stride=1
        )
        # self.norm_wx = nn.GroupNorm(num_groups=32, num_channels=out_channels, affine=True)
        # self.norm_wx = nn.InstanceNorm2d(out_channels, affine=True)
        self.norm_wx = nn.BatchNorm2d(out_channels)
        self.psi = nn.Conv2d(
            in_channels=out_channels,
            out_channels=1,
            bias=True,
            padding=0,
            kernel_size=1,
            stride=1,
        )
        # self.norm_psi = nn.GroupNorm(num_groups=32, num_channels=out_channels, affine=True)
        # self.norm_psi = nn.InstanceNorm2d(out_channels, affine=True)
        self.norm_psi = nn.BatchNorm2d(1)

    def forward(self, g, x):
        g1 = self.wg(g)
        g1 = self.norm_wg(g1)
        x1 = self.wx(x)
        x1 = self.norm_wx(x1)
        psi = F.relu(g1 + x1, inplace=True)
        psi = self.psi(psi)
        psi = self.norm_psi(psi)
        psi = torch.sigmoid(psi)
        return x * psi


class ConvBlock2D(nn.Module):
    def __init__(self, in_channels, out_channels, dropout, **kwargs):
        super(ConvBlock2D, self).__init__()
        self.conv1 = BasicConv2d(
            in_channels=in_channels, out_channels=out_channels, dropout=dropout
        )
        self.conv2 = BasicConv2d(
            in_channels=out_channels, out_channels=out_channels, dropout=dropout
        )

    def forward(self, input):
        x1 = self.conv1(input)
        x2 = self.conv2(x1)
        return x2


class AttentionUNet(nn.Module):
    def __init__(self, params, num_classes):
        super(AttentionUNet, self).__init__()
        # num_classes = params.dict['num_classes_bc']
        dropout_rate = params.dict["dropout_rate"]

        self.max_pool_2x2 = nn.MaxPool2d(kernel_size=2, stride=2)
        # self.down_conv_1 = double_conv(1, 32, dropout_rate)
        self.down1 = ConvBlock2D(1, 32, dropout_rate)
        # self.down_conv_2 = double_conv(32, 64, dropout_rate)
        self.down2 = ConvBlock2D(32, 64, dropout_rate)
        # self.down_conv_3 = double_conv(64, 128, dropout_rate)
        self.down3 = ConvBlock2D(64, 128, dropout_rate)
        # self.down_conv_4 = double_conv(128, 256, dropout_rate)
        self.down4 = ConvBlock2D(128, 256, dropout_rate)
        # self.down_conv_5 = double_conv(256, 512, dropout_rate)
        self.down5 = ConvBlock2D(256, 512, dropout_rate)

        self.up_trans_5 = nn.ConvTranspose2d(
            in_channels=512, out_channels=256, kernel_size=2, stride=2
        )

        # self.up_conv_1 = double_conv(512, 256, dropout_rate)
        self.up5 = ConvBlock2D(512, 256, dropout_rate)
        self.ag5 = AttentionGate2D(256, 256, 128)

        self.up_trans_4 = nn.ConvTranspose2d(
            in_channels=256, out_channels=128, kernel_size=2, stride=2
        )

        # self.up_conv_2 = double_conv(256, 128, dropout_rate)
        self.up4 = ConvBlock2D(256, 128, dropout_rate)
        self.ag4 = AttentionGate2D(128, 128, 64)
        self.up_trans_3 = nn.ConvTranspose2d(
            in_channels=128, out_channels=64, kernel_size=2, stride=2
        )

        # self.up_conv_3 = double_conv(128, 64, dropout_rate)
        self.up3 = ConvBlock2D(128, 64, dropout_rate)
        self.ag3 = AttentionGate2D(64, 64, 32)

        self.up_trans_2 = nn.ConvTranspose2d(
            in_channels=64, out_channels=32, kernel_size=2, stride=2
        )

        # self.up_conv_4 = double_conv(64, 32, dropout_rate)
        self.up2 = ConvBlock2D(64, 32, dropout_rate)
        self.ag2 = AttentionGate2D(32, 32, 32)
        self.out = nn.Conv2d(in_channels=32, out_channels=num_classes, kernel_size=1)

    def forward(self, image):

        x1 = self.down1(image)
        # after each convolution apply max_pooling
        p1 = self.max_pool_2x2(x1)

        x2 = self.down2(p1)
        p2 = self.max_pool_2x2(x2)

        x3 = self.down3(p2)
        p3 = self.max_pool_2x2(x3)

        x4 = self.down4(p3)
        p4 = self.max_pool_2x2(x4)

        x5 = self.down5(p4)

        # decoder
        u6 = self.up_trans_5(x5)
        s4 = self.ag5(g=u6, x=x4)
        x6 = self.up5(torch.cat([u6, s4], 1))

        u7 = self.up_trans_4(x6)
        s3 = self.ag4(u7, x3)
        x7 = self.up4(torch.cat([u7, s3], 1))

        u8 = self.up_trans_3(x7)
        s2 = self.ag3(u8, x2)
        x8 = self.up3(torch.cat([u8, s2], 1))

        u9 = self.up_trans_2(x8)
        s1 = self.ag2(u9, x1)
        x9 = self.up2(torch.cat([u9, s1], 1))

        x = self.out(x9)
        x = F.softmax(x, dim=1)
        return x